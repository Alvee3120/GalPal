from django.core.exceptions import ValidationError


def field_error(field, message, code):
    """A `ValidationError` on one field whose `code` survives (dict-form errors drop a top-level code)."""
    return ValidationError({field: ValidationError(message, code=code)})
