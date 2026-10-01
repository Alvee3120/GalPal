"""
Writing audit entries. `record(...)` can be called from anywhere (services, signals): the acting user and IP come
from the current request (`context`), unless passed explicitly. It never raises into the caller.
"""

import json
import logging
import re
from contextvars import ContextVar
from decimal import Decimal

from django.db import transaction

from .models import AuditLog

logger = logging.getLogger(__name__)

_current_request = ContextVar("audit_request", default=None)

STAFF_ROLES = {"admin", "cce"}
REDACTED = "[redacted]"
# Request-body keys whose values never reach the log (passwords, tokens, API secrets, one-time codes).
SECRET_KEY = re.compile(r"(password|token|secret|^otp$|^access$|^refresh$|api_key|^code$)", re.IGNORECASE)
MAX_BODY_CHARS = 4000


def set_request(request):
    return _current_request.set(request)


def reset_request(token):
    _current_request.reset(token)


def current_request():
    return _current_request.get()


def client_ip(request):
    """REMOTE_ADDR; behind the production proxy the first X-Forwarded-For hop (only trusted when configured)."""
    from django.conf import settings

    if request is None:
        return None
    if getattr(settings, "AUDIT_TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def _plain(value):
    """JSON-safe copy (Decimals, dates, models → strings)."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return str(value)


def redact(data):
    if isinstance(data, dict):
        return {k: (REDACTED if SECRET_KEY.search(str(k)) else redact(v)) for k, v in data.items()}
    if isinstance(data, list):
        return [redact(v) for v in data]
    return data


def diff(before, after):
    """{"field": [old, new]} for the keys whose value changed."""
    before, after = before or {}, after or {}
    return {key: [_plain(before.get(key)), _plain(after.get(key))] for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)}


def record(action, *, target=None, target_type="", target_id="", target_label="", changes=None, metadata=None, actor=None, request=None):
    """Write one audit entry. `target` (a model instance) fills type/id/label. Returns the entry, or None on failure."""
    try:
        request = request if request is not None else current_request()
        if actor is None and request is not None:
            user = getattr(request, "user", None)
            actor = user if user is not None and user.is_authenticated else None
        if target is not None:
            target_type = target_type or target._meta.model_name
            target_id = target_id or str(target.pk)
            target_label = target_label or str(getattr(target, "number", None) or target)
        with transaction.atomic():  # own savepoint: a failed insert can't poison the caller's transaction
            return AuditLog.objects.create(
                actor=actor,
                actor_name=(getattr(actor, "full_name", "") or getattr(actor, "phone", "") or "")[:150] if actor else "",
                actor_role=getattr(actor, "role", "") if actor else "",
                action=action[:60],
                target_type=target_type[:40], target_id=str(target_id)[:40], target_label=str(target_label)[:200],
                changes=_plain(changes or {}), metadata=_plain(redact(metadata or {})),
                ip_address=client_ip(request),
                user_agent=(request.META.get("HTTP_USER_AGENT", "") if request is not None else "")[:300],
            )
    except Exception:  # noqa: BLE001 - auditing must never break the action itself
        logger.exception("Could not write the audit entry %s", action)
        return None


def request_body(request):
    """The JSON body of a write, redacted and size-capped; file uploads are summarised by field name only."""
    content_type = request.META.get("CONTENT_TYPE", "")
    if content_type.startswith("multipart/") or content_type.startswith("application/x-www-form-urlencoded"):
        try:
            return {"form_fields": sorted(request.POST.keys()), "files": sorted(request.FILES.keys())}
        except Exception:  # noqa: BLE001
            return {"form": "unreadable"}
    raw = getattr(request, "_audit_body", b"") or b""
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {"body": "not JSON"}
    text = json.dumps(_plain(redact(data)), ensure_ascii=False)
    if len(text) > MAX_BODY_CHARS:
        return {"body_truncated": text[:MAX_BODY_CHARS]}
    return redact(data)
