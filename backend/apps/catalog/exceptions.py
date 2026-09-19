from rest_framework import status
from rest_framework.exceptions import APIException


class Conflict(APIException):
    """409: the request is valid but conflicts with existing data. Carries structured `details`."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with existing data."
    default_code = "conflict"

    def __init__(self, detail=None, code=None, details=None):
        super().__init__(detail, code)
        self.details = details
