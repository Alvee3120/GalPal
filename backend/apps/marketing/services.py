"""
Marketing/tracking business logic: hashing user data per Meta's rules, sending one event to Meta
CAPI or GA4, and logging every attempt. `tasks.py` is the only caller in production (so a send is
always retried on a transient failure); tests and the admin "resend" action may call these directly.

Every send is idempotent under the `event_id` a caller supplies: a second attempt for an event
already logged as successful is skipped rather than sent twice, which matters most for `Purchase`
(the order-placed signal firing more than once should never double-report a sale to either platform).
"""
import hashlib
import logging

from django.utils import timezone

from apps.site_settings.services import get_site_settings

from .models import TrackingDestination, TrackingEventLog

logger = logging.getLogger(__name__)

META_API_VERSION = "v21.0"
META_EVENTS_URL = "https://graph.facebook.com/{version}/{pixel_id}/events"
GA4_COLLECT_URL = "https://www.google-analytics.com/mp/collect"
REQUEST_TIMEOUT = 5


# --- Meta's user-data hashing rules ------------------------------------------------------------------------


def _hash(value):
    """SHA-256 of a normalized (trimmed, lower-cased) value. Blank/None -> None (never hash nothing)."""
    text = (str(value) if value is not None else "").strip().lower()
    return hashlib.sha256(text.encode()).hexdigest() if text else None


def _hash_phone(phone):
    """Meta wants digits only, with country code, no symbols. `phone` is already the app's canonical `01XXXXXXXXX`."""
    if not phone:
        return None
    digits = "".join(ch for ch in str(phone) if ch.isdigit())
    if digits.startswith("0"):
        digits = "88" + digits  # Bangladesh: 01XXXXXXXXX -> 8801XXXXXXXXX, Meta's expected E.164-without-plus form
    return _hash(digits)


def build_user_data(*, user=None, email="", phone="", name="", fbp="", fbc="", client_ip="", user_agent=""):
    """
    Meta's `user_data` object. Explicit `email`/`phone`/`name` win; otherwise they come from `user`
    (a logged-in customer). `fbp`/`fbc`/`client_ip`/`client_user_agent` are never hashed — Meta uses
    them as-is for matching. The result never contains an unhashed piece of PII.
    """
    email = email or (getattr(user, "email", "") or "")
    phone = phone or (getattr(user, "phone", "") or "")
    name = (name or (getattr(user, "full_name", "") or "")).strip()
    first, _, last = name.partition(" ")

    data = {}
    if _hash(email):
        data["em"] = [_hash(email)]
    if _hash_phone(phone):
        data["ph"] = [_hash_phone(phone)]
    if _hash(first):
        data["fn"] = [_hash(first)]
    if _hash(last):
        data["ln"] = [_hash(last)]
    if fbp:
        data["fbp"] = fbp
    if fbc:
        data["fbc"] = fbc
    if client_ip:
        data["client_ip_address"] = client_ip
    if user_agent:
        data["client_user_agent"] = user_agent
    return data


# --- sending -----------------------------------------------------------------------------------------------------


def _safe_json(response):
    try:
        return response.json()
    except ValueError:  # GA4's success response is 204 No Content: no body to parse
        return {}


def _log(*, event_name, destination, event_id, order, user, is_manual_order, payload, status_code, body, success, error_message, attempt):
    return TrackingEventLog.objects.create(
        event_name=event_name, destination=destination, event_id=event_id or "", order=order,
        user=user if user and getattr(user, "pk", None) else None, is_manual_order=is_manual_order,
        request_payload=payload, response_status=status_code, response_body=body, success=success,
        error_message=(error_message or "")[:500], attempt=attempt,
    )


def _already_sent(event_id, event_name, destination):
    return bool(event_id) and TrackingEventLog.objects.filter(event_id=event_id, event_name=event_name, destination=destination, success=True).exists()


def send_meta_event(*, event_name, event_id="", user_data, custom_data=None, event_source_url="", order=None, user=None, is_manual_order=False, attempt=1):
    """
    POST one event to Meta's Conversions API. Returns the `TrackingEventLog` row. Raises
    `requests.RequestException` only for a network-level failure (so Celery retries it); a
    configuration problem or a rejection from Meta itself is logged as failed but never retried,
    since retrying an invalid token or a malformed payload can never succeed.
    """
    import requests

    site = get_site_settings()
    if not site.meta_pixel_id or not site.meta_capi_access_token:
        return _log(event_name=event_name, destination=TrackingDestination.META_CAPI, event_id=event_id, order=order, user=user,
                     is_manual_order=is_manual_order, payload={}, status_code=None, body={}, success=False,
                     error_message="Meta Conversions API is not configured (missing pixel id or access token).", attempt=attempt)
    if _already_sent(event_id, event_name, TrackingDestination.META_CAPI):
        return _log(event_name=event_name, destination=TrackingDestination.META_CAPI, event_id=event_id, order=order, user=user,
                     is_manual_order=is_manual_order, payload={}, status_code=None, body={}, success=True,
                     error_message="Skipped: already sent (event_id already succeeded).", attempt=attempt)

    event = {
        "event_name": event_name, "event_time": int(timezone.now().timestamp()), "event_id": event_id or "",
        "action_source": "website", "user_data": user_data,
    }
    if event_source_url:
        event["event_source_url"] = event_source_url
    if custom_data:
        event["custom_data"] = custom_data
    payload = {"data": [event]}
    if site.meta_capi_test_event_code:
        payload["test_event_code"] = site.meta_capi_test_event_code

    url = META_EVENTS_URL.format(version=META_API_VERSION, pixel_id=site.meta_pixel_id)
    try:
        response = requests.post(url, params={"access_token": site.meta_capi_access_token}, json=payload, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        _log(event_name=event_name, destination=TrackingDestination.META_CAPI, event_id=event_id, order=order, user=user,
             is_manual_order=is_manual_order, payload=payload, status_code=None, body={}, success=False, error_message=str(exc), attempt=attempt)
        raise

    body = _safe_json(response)
    success = response.status_code < 300 and "error" not in body
    error_message = "" if success else str(body.get("error", {}).get("message") or body or f"HTTP {response.status_code}")
    return _log(event_name=event_name, destination=TrackingDestination.META_CAPI, event_id=event_id, order=order, user=user,
                is_manual_order=is_manual_order, payload=payload, status_code=response.status_code, body=body,
                success=success, error_message=error_message, attempt=attempt)


def send_ga4_event(*, event_name, client_id, params=None, order=None, user=None, is_manual_order=False, attempt=1):
    """POST one event to the GA4 Measurement Protocol. Same retry contract as `send_meta_event`."""
    import requests

    site = get_site_settings()
    if not site.ga4_measurement_id or not site.ga4_api_secret:
        return _log(event_name=event_name, destination=TrackingDestination.GA4, event_id="", order=order, user=user,
                     is_manual_order=is_manual_order, payload={}, status_code=None, body={}, success=False,
                     error_message="GA4 is not configured (missing measurement id or api secret).", attempt=attempt)

    ga4_event_name = "purchase" if event_name == "Purchase" else event_name.lower()
    payload = {"client_id": str(client_id or "server"), "events": [{"name": ga4_event_name, "params": params or {}}]}
    try:
        response = requests.post(
            GA4_COLLECT_URL, params={"measurement_id": site.ga4_measurement_id, "api_secret": site.ga4_api_secret},
            json=payload, timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        _log(event_name=event_name, destination=TrackingDestination.GA4, event_id="", order=order, user=user,
             is_manual_order=is_manual_order, payload=payload, status_code=None, body={}, success=False, error_message=str(exc), attempt=attempt)
        raise

    success = response.status_code < 300
    return _log(event_name=event_name, destination=TrackingDestination.GA4, event_id="", order=order, user=user,
                is_manual_order=is_manual_order, payload=payload, status_code=response.status_code, body=_safe_json(response),
                success=success, error_message="" if success else f"HTTP {response.status_code}", attempt=attempt)
