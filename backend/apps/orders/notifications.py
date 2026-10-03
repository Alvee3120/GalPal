"""
Messages the order flow sends — now through Module 16 (apps.notifications): templates, NotificationLog, retries.

Nothing here may ever raise into the checkout request, and the generated password must never be logged: the
notification log keeps the message with the password masked.
"""
from apps.notifications import services as notifications


def send_new_account_email(user, password):
    """
    "Your account details": the login and the generated password (email, and SMS when that template is switched on),
    with a prompt to change it. Called after the order's transaction has committed. True if a message was sent.
    """
    logs = notifications.new_account(user, password)
    return any(log.status == "sent" for log in logs)
