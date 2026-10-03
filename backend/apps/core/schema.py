"""OpenAPI post-processing (Module 18): every operation lands in a named Swagger/Postman folder."""

# Operations a view never tagged fall back to their first path segment ("admin", "auth"); file them properly.
UNTAGGED_BY_PATH = [
    ("/api/v1/auth/", "Auth"),
    ("/api/v1/admin/products/", "Admin – Products"),
    ("/api/v1/admin/attribute-values/", "Admin – Products"),
    ("/api/v1/admin/stock-movements/", "Admin – Products"),
    ("/api/v1/admin/coupon-usages/", "Admin – Coupons"),
]


def retag_untagged(result, generator, request, public):
    for path, operations in result.get("paths", {}).items():
        for operation in operations.values():
            if not isinstance(operation, dict):
                continue
            tags = operation.get("tags") or []
            if tags and tags[0][:1].isupper():
                continue
            for prefix, tag in UNTAGGED_BY_PATH:
                if path.startswith(prefix):
                    operation["tags"] = [tag]
                    break
    return result
