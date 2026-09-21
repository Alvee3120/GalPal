"""
Messages the order flow sends. Module 16 (Notifications) will turn these into Celery tasks with a
`NotificationLog`; the functions here are the seam it replaces, so callers don't change.

Nothing here may ever raise into the checkout request, and the generated password must never be
logged: on failure only the user id is recorded.
"""
import logging

from django.core.mail import send_mail

from apps.site_settings.services import get_site_settings

logger = logging.getLogger(__name__)


def send_new_account_email(user, password):
    """
    "Your GalPal account details": the login identifier and the generated password, with a prompt
    to change it. Called after the order's transaction has committed. Returns True if it was handed
    to the mail backend. A failure is logged (without the password) and swallowed: the order stands
    and the customer can use "forgot password".
    """
    if not user.email:
        return False
    try:
        site_name = get_site_settings().site_name
        body = (
            f"Hello {user.full_name},\n\n"
            f"Thank you for your order. We created a {site_name} account so you can track it and order faster.\n\n"
            f"  Login: {user.phone}  (or {user.email})\n"
            f"  Password: {password}\n\n"
            "You will be asked to change this password the first time you log in. "
            "If you ever forget it, use \"Forgot password\" on the login page.\n\n"
            f"— {site_name}"
        )
        send_mail(f"Your {site_name} account details", body, None, [user.email], fail_silently=False)
    except Exception:  # noqa: BLE001 - must never break checkout; deliberately no exc_info (it could echo the body)
        logger.error("Could not send the new-account email to user %s", user.pk)
        return False
    return True
