from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied


class InvalidCredentials(APIException):
    # A plain APIException so it stays 401 even on views without an authenticate header.
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Invalid phone/email or password."
    default_code = "invalid_credentials"


class AccountDisabled(PermissionDenied):
    default_detail = "This account has been deactivated. Please contact support."
    default_code = "account_disabled"


class InvalidOTP(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The code is invalid or has expired."
    default_code = "invalid_otp"


class AccountAlreadyExists(Exception):
    """Raised by `create_customer_account`; callers decide how (or whether) to surface it."""

    def __init__(self, field):
        super().__init__(f"An account with this {field} already exists.")
        self.field = field
