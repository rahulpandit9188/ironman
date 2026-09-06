import uuid
from datetime import date

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


def paginated_response(queryset, request, serializer_class, message):
    paginator = CustomPagination()
    page = paginator.paginate_queryset(queryset, request)
    serializer = serializer_class(page, many=True)

    return Response(
        {
            "message": message,
            "data": serializer.data,
            "pagination": {
                "count": paginator.page.paginator.count,
                "page": paginator.page.number,
                "page_size": paginator.get_page_size(request),
                "total_pages": paginator.page.paginator.num_pages,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
            },
        },
        status=status.HTTP_200_OK,
    )


def apply_ordering(queryset, ordering, allowed_fields, default):
    if ordering:
        field = ordering.removeprefix("-")
        if field in allowed_fields:
            return queryset.order_by(ordering)
    return queryset.order_by(default)


def valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def valid_date(value):
    try:
        date.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False