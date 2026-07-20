"""
API истории поиска пользователя.

SearchHistoryView   — GET/POST/DELETE /api/v1/catalog/search-history/
SearchHistoryItemView — DELETE /api/v1/catalog/search-history/<id>/

История персональная (требует аутентификации). GET отдаёт последние
уникальные запросы (свежий сверху), POST сохраняет запрос, DELETE
очищает всю историю или один запрос.
"""

from typing import ClassVar, cast

from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import SearchQuery
from apps.users.models import User

# Сколько уникальных запросов показывать в истории.
HISTORY_LIMIT = 10


class SearchHistoryView(APIView):
    """История поиска: получить, сохранить, очистить."""

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]  # type: ignore[misc]

    def get(self, request: Request) -> Response:
        """
        Последние уникальные запросы пользователя (свежий сверху).

        Дубликаты схлопываем в Python: идём по запросам от свежих к
        старым, берём первое вхождение каждого текста, до лимита.
        """
        user = cast(User, request.user)
        seen: set[str] = set()
        result: list[dict[str, object]] = []
        for sq in user.search_queries.all():  # уже отсортированы -created_at
            key = sq.query.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append({"id": sq.id, "query": sq.query})
            if len(result) >= HISTORY_LIMIT:
                break
        return Response(result, status=status.HTTP_200_OK)

    def post(self, request: Request) -> Response:
        """Сохранить запрос. Пустой запрос игнорируется."""
        user = cast(User, request.user)
        query = str(request.data.get("query", "")).strip()
        if not query:
            return Response(
                {"error": {"code": "empty_query", "message": "Запрос пуст."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sq = SearchQuery.objects.create(user=user, query=query)
        return Response(
            {"id": sq.id, "query": sq.query},
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request: Request) -> Response:
        """Очистить всю историю поиска пользователя."""
        user = cast(User, request.user)
        user.search_queries.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SearchHistoryItemView(APIView):
    """Удаление одного запроса из истории."""

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]  # type: ignore[misc]

    def delete(self, request: Request, query_id: int) -> Response:
        """Удалить один запрос по id (только свой)."""
        user = cast(User, request.user)
        deleted, _ = SearchQuery.objects.filter(
            id=query_id,
            user=user,
        ).delete()
        if deleted == 0:
            return Response(
                {"error": {"code": "not_found", "message": "Запрос не найден."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
