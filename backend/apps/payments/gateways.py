"""
Payment gateway interface: `initiate` (start a charge and hand back where to send the customer),
`parse_callback` (verify and normalize an IPN/webhook), and `verify` (ask the gateway directly, for
when a webhook is missed or as a manual reconciliation). One gateway here is a genuine plug-in point;
`StubGateway` is a deterministic, no-network stand-in for a bKash/SSLCommerz-style redirect+webhook
flow, wired through the exact same three methods a real integration would implement.

A new gateway is added to `settings.PAYMENT_GATEWAYS` (slug -> dotted class path) and picked up by
`get_gateway(slug)` — nothing else in this app needs to change.
"""
import hashlib
import hmac
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings
from django.utils.module_loading import import_string


class GatewayError(Exception):
    """Base for gateway-layer problems; `code` becomes the API error envelope's `code`."""

    def __init__(self, message, code="gateway_error"):
        super().__init__(message)
        self.message, self.code = message, code


class InvalidSignature(GatewayError):
    def __init__(self, message="The callback signature could not be verified."):
        super().__init__(message, code="invalid_signature")


@dataclass(frozen=True)
class InitiateResult:
    reference: str
    redirect_url: str
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GatewayResult:
    """The outcome of a callback or a `verify` call, in one normalized shape."""

    reference: str
    outcome: str  # "success" | "failed" | "pending"
    amount: Decimal | None
    raw: dict = field(default_factory=dict)


class PaymentGateway(ABC):
    """Real gateways subclass this; `StubGateway` below shows the shape."""

    slug: str

    @abstractmethod
    def initiate(self, payment) -> InitiateResult:
        """Start a charge for `payment.amount` and return where to send the customer."""

    @abstractmethod
    def parse_callback(self, raw_body: bytes, headers: dict) -> GatewayResult:
        """Verify and normalize an IPN/webhook. Raise `InvalidSignature` if it doesn't check out."""

    @abstractmethod
    def verify(self, payment) -> GatewayResult:
        """Ask the gateway directly what a payment's status is."""


class StubGateway(PaymentGateway):
    """
    A no-network stand-in: `initiate` returns a fake redirect URL; the "gateway" is really whoever
    POSTs to the callback URL with a valid HMAC signature (`PAYMENT_STUB_GATEWAY_SECRET`) — a test,
    or a person manually driving a demo. `verify` has no external system to ask, so it replays the
    last callback this payment received.
    """

    slug = "stub"

    def _sign(self, raw_body: bytes) -> str:
        return hmac.new(settings.PAYMENT_STUB_GATEWAY_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()

    def initiate(self, payment) -> InitiateResult:
        reference = f"STUB-{uuid.uuid4().hex[:16].upper()}"
        base = settings.PAYMENT_STUB_GATEWAY_BASE_URL.rstrip("/")
        return InitiateResult(reference=reference, redirect_url=f"{base}/{reference}/", raw={"amount": str(payment.amount)})

    def parse_callback(self, raw_body: bytes, headers: dict) -> GatewayResult:
        signature = headers.get("X-Stub-Signature", "")
        if not signature or not hmac.compare_digest(signature, self._sign(raw_body)):
            raise InvalidSignature()
        try:
            data = json.loads(raw_body)
            reference = str(data["reference"])
            outcome = data["status"]
            amount = Decimal(str(data["amount"])) if data.get("amount") is not None else None
        except (KeyError, ValueError, TypeError, json.JSONDecodeError):
            raise GatewayError("Malformed callback payload.", code="malformed_callback") from None
        if outcome not in ("success", "failed"):
            raise GatewayError("Unknown callback status.", code="malformed_callback")
        return GatewayResult(reference=reference, outcome=outcome, amount=amount, raw=data)

    def verify(self, payment) -> GatewayResult:
        last = (payment.gateway_payload or {}).get("last_callback")
        if not last:
            return GatewayResult(reference=payment.transaction_id, outcome="pending", amount=None, raw={})
        amount = Decimal(str(last["amount"])) if last.get("amount") is not None else None
        return GatewayResult(reference=last.get("reference", payment.transaction_id), outcome=last.get("status", "pending"), amount=amount, raw=last)


def get_gateway(slug):
    try:
        path = settings.PAYMENT_GATEWAYS[slug]
    except KeyError:
        raise GatewayError(f"Unknown payment gateway: {slug}.", code="unknown_gateway") from None
    return import_string(path)()
