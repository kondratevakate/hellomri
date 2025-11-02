"""Конфигурация метрик Prometheus для приложения.

Этот модуль настраивает и конфигурирует метрики Prometheus для мониторинга приложения.
"""

from prometheus_client import Counter, Histogram, Gauge
from starlette_prometheus import metrics, PrometheusMiddleware

# Метрики HTTP-запросов
# Счетчик: http_requests_total
# Тип: Counter (Счетчик)
# Назначение: Подсчитывает общее количество HTTP-запросов.
# Метки (labels): method (GET, POST и т.д.), endpoint (путь к эндпоинту), status (HTTP-код ответа).
# Пример: http_requests_total{method="GET", endpoint="/api/users", status="200"} 10
http_requests_total = Counter("http_requests_total", "Общее количество HTTP-запросов", ["method", "endpoint", "status"])

# Гистограмма: http_request_duration_seconds
# Тип: Histogram (Гистограмма)
# Назначение: Измеряет длительность HTTP-запросов в секундах.
# Метки: method, endpoint.
# Гистограммы автоматически создают метрики для квантилей (например, 0.5, 0.9, 0.99) и счетчик общего количества событий.
# Пример: http_request_duration_seconds_sum{method="POST", endpoint="/api/chat"} 2.5 (суммарное время)
#         http_request_duration_seconds_count{method="POST", endpoint="/api/chat"} 5 (количество запросов)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "Длительность HTTP-запроса в секундах", ["method", "endpoint"]
)

# Метрики базы данных
# Гейдж: db_connections
# Тип: Gauge (Гейдж)
# Назначение: Показывает текущее количество активных соединений с базой данных.
# Значение гейджа может увеличиваться или уменьшаться.
# Пример: db_connections 15
db_connections = Gauge("db_connections", "Количество активных соединений с базой данных")

# Пользовательские бизнес-метрики
# Счетчик: orders_processed
# Тип: Counter
# Назначение: Подсчитывает общее количество обработанных заказов.
# Пример: orders_processed_total 100
orders_processed = Counter("orders_processed_total", "Общее количество обработанных заказов")

# Гистограмма: llm_inference_duration_seconds
# Тип: Histogram
# Назначение: Измеряет время, затраченное на обработку одного (непотокового) вызова LLM.
# Метки: model (имя используемой LLM-модели).
# buckets: Задает пользовательские интервалы (бакеты) для гистограммы.
# Пример: llm_inference_duration_seconds_bucket{model="gpt-4", le="1.0"} 8 (8 вызовов заняли <= 1.0 секунды)
llm_inference_duration_seconds = Histogram(
    "llm_inference_duration_seconds",
    "Время, затраченное на обработку вызова LLM",
    ["model"],
    buckets=[0.1, 0.3, 0.5, 1.0, 2.0, 5.0] # Определенные пользователем бакеты
)


# Гистограмма: llm_stream_duration_seconds
# Тип: Histogram
# Назначение: Измеряет время, затраченное на обработку одного потокового вызова LLM (например, SSE).
# Метки: model.
# buckets: Другой набор бакетов, подходящий для потоковых вызовов, которые могут быть дольше.
# Пример: llm_stream_duration_seconds_count{model="claude-3", le="+Inf"} 3 (всего 3 потоковых вызова)
llm_stream_duration_seconds = Histogram(
    "llm_stream_duration_seconds",
    "Время, затраченное на обработку потокового вызова LLM",
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0] # Другой набор бакетов
)


def setup_metrics(app):
    """Настроить промежуточное ПО (middleware) и эндпоинт метрик Prometheus.

    Args:
        app: Экземпляр приложения FastAPI
    """
    # Добавить промежуточное ПО Prometheus
    # Это ПО автоматически собирает базовые метрики (например, длительность и количество запросов)
    # при каждом входящем и исходящем HTTP-запросе.
    app.add_middleware(PrometheusMiddleware)

    # Добавить эндпоинт для получения метрик
    # По адресу /metrics будет доступен вывод всех собранных метрик в формате, понятном Prometheus.
    app.add_route("/metrics", metrics)

