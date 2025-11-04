"""Пользовательское промежуточное ПО (middleware) для отслеживания метрик и других сквозных задач."""

import time
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.metrics import (
    http_requests_total,              # Импортируем счетчик общего количества HTTP-запросов
    http_request_duration_seconds,    # Импортируем гистограмму длительности HTTP-запросов
    db_connections,                   # Импортируем гейдж количества соединений с БД (хотя в этом коде не используется)
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Промежуточное ПО для отслеживания метрик HTTP-запросов."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Отслеживает метрики для каждого запроса.

        Args:
            request: Входящий HTTP-запрос
            call_next: Следующий компонент в цепочке обработки (другое middleware или конечный обработчик маршрута)

        Returns:
            Response: Ответ от приложения
        """
        # Запоминаем время начала обработки запроса
        start_time = time.time()

        try:
            # Передаем управление следующему компоненту (middleware или эндпоинту)
            response = await call_next(request)
            # Получаем статус-код из ответа
            status_code = response.status_code
        except Exception:
            # Если во время обработки запроса произошло исключение,
            # считаем, что это ошибка сервера (500)
            status_code = 500
            # Важно: повторно вызываем raise, чтобы исключение не заглушалось
            raise
        finally:
            # Вычисляем общую длительность обработки запроса
            duration = time.time() - start_time

            # Записываем метрики

            # Увеличиваем счетчик HTTP-запросов, добавляя метки:
            # - method: HTTP-метод (GET, POST и т.д.)
            # - endpoint: путь к эндпоинту (например, /api/users)
            # - status: HTTP-статус ответа (например, 200, 404, 500)
            http_requests_total.labels(
                method=request.method,
                endpoint=request.url.path,
                status=status_code
            ).inc() # .inc() увеличивает счетчик на 1

            # Фиксируем длительность запроса в гистограмме, добавляя метки:
            # - method: HTTP-метод
            # - endpoint: путь к эндпоинту
            http_request_duration_seconds.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration) # .observe(duration) записывает значение длительности

        # Возвращаем полученный от следующего компонента ответ
        return response

