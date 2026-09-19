from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """
    Page-number pagination used by every list endpoint.

    `?page=2&page_size=50` — default 20 per page, capped at 100.
    Response shape: `{count, next, previous, results}`.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
