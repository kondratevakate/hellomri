"""Оценщик для evals."""

import asyncio
import os
import sys
import time
from datetime import (
    datetime,
    timedelta,
)
from time import sleep

import openai
from langfuse import Langfuse
# Импорт типа данных для подробной информации о трассировке
from langfuse.api.resources.commons.types.trace_with_details import TraceWithDetails
# Библиотека для отображения прогресс-баров
from tqdm import tqdm

# --- Настройка импорта ---
# Добавляем корневую директорию проекта в путь поиска модулей,
# чтобы можно было импортировать из папки app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импорты настроек, логгера и вспомогательных функций/схем
from app.core.config import settings
from app.core.logging import logger
from evals.helpers import (
    calculate_avg_scores,      # Функция для вычисления средних оценок
    generate_report,           # Функция для генерации итогового отчета
    get_input_output,          # Функция для извлечения входных и выходных данных из трассировки
    initialize_metrics_summary, # Функция для инициализации сводки по метрикам в отчете
    initialize_report,         # Функция для инициализации структуры отчета
    process_trace_results,     # Функция для обработки результатов оценки трассировки
    update_failure_metrics,    # Функция для обновления статистики неудачных оценок
    update_success_metrics,    # Функция для обновления статистики успешных оценок
)
from evals.metrics import metrics  # Словарь/список определений метрик
from evals.schemas import ScoreSchema # Pydantic-схема для структурирования оценки


class Evaluator:
    """Оценивает выводы модели с использованием предопределенных метрик.

    Этот класс отвечает за получение трассировок из Langfuse, их оценку по
    заданным метрикам и загрузку оценок обратно в Langfuse.

    Атрибуты:
        client: Асинхронный клиент OpenAI для вызовов API.
        langfuse: Клиент Langfuse для управления трассировками.
    """

    def __init__(self):
        """Инициализирует Evaluator с клиентами OpenAI и Langfuse."""
        # Инициализация клиента OpenAI для оценки (использует отдельные ключи)
        self.client = openai.AsyncOpenAI(api_key=settings.EVALUATION_API_KEY, base_url=settings.EVALUATION_BASE_URL)
        # Инициализация клиента Langfuse для работы с трассировками и оценками
        self.langfuse = Langfuse(public_key=settings.LANGFUSE_PUBLIC_KEY, secret_key=settings.LANGFUSE_SECRET_KEY)
        # Инициализация структуры отчета с указанием используемой LLM
        self.report = initialize_report(settings.EVALUATION_LLM)
        # Добавление начальных значений для подсчета метрик в отчет
        initialize_metrics_summary(self.report, metrics)

    async def run(self, generate_report_file=True):
        """Основная функция выполнения, которая получает и оценивает трассировки.

        Извлекает трассировки из Langfuse, оценивает каждую по всем метрикам
        и загружает оценки обратно в Langfuse.

        Args:
            generate_report_file: Генерировать ли JSON-отчет после оценки. По умолчанию True.
        """
        start_time = time.time()  # Засекаем время начала
        # Получаем список трассировок для оценки
        traces = self.__fetch_traces()
        self.report["total_traces"] = len(traces) # Сохраняем общее количество трассировок

        # Словарь для хранения результатов оценки по каждой трассировке
        trace_results = {}

        # Проходим по каждой трассировке
        for trace in tqdm(traces, desc="Оценка трассировок"):
            trace_id = trace.id
            # Инициализируем статистику для текущей трассировки
            trace_results[trace_id] = {
                "success": False, # Успешно ли оценена трассировка (все метрики пройдены?)
                "metrics_evaluated": 0, # Сколько метрик было протестировано
                "metrics_succeeded": 0, # Сколько метрик успешно оценено
                "metrics_results": {},  # Результаты по каждой метрике
            }

            # Применяем каждую метрику к текущей трассировке
            for metric in tqdm(metrics, desc=f"Применение метрик к трассировке {trace_id[:8]}...", leave=False):
                metric_name = metric["name"]
                # Извлекаем входные и выходные данные из трассировки
                input, output = get_input_output(trace)
                # Запускаем оценку по текущей метрике
                score = await self._run_metric_evaluation(metric, input, output)

                if score:
                    # Если оценка успешна, отправляем её в Langfuse
                    self._push_to_langfuse(trace, score, metric)
                    # Обновляем статистику успешной оценки
                    update_success_metrics(self.report, trace_id, metric_name, score, trace_results)
                else:
                    # Если оценка не удалась, обновляем статистику неудач
                    update_failure_metrics(self.report, trace_id, metric_name, trace_results)

                # Увеличиваем счетчик протестированных метрик
                trace_results[trace_id]["metrics_evaluated"] += 1

            # Обрабатываем итоговые результаты для текущей трассировки
            process_trace_results(self.report, trace_id, trace_results, len(metrics))
            # Задержка между оценками трассировок, чтобы не перегружать API
            sleep(settings.EVALUATION_SLEEP_TIME)

        # Вычисляем общее время выполнения
        self.report["duration_seconds"] = round(time.time() - start_time, 2)
        # Вычисляем средние оценки по всем метрикам
        calculate_avg_scores(self.report)

        # Если запрошено, генерируем итоговый отчет в файл
        if generate_report_file:
            generate_report(self.report)

        # Логируем итоговую статистику
        logger.info(
            "Оценка завершена",
            total_traces=self.report["total_traces"],
            successful_traces=self.report["successful_traces"],
            failed_traces=self.report["failed_traces"],
            duration_seconds=self.report["duration_seconds"],
        )

    def _push_to_langfuse(self, trace: TraceWithDetails, score: ScoreSchema, metric: dict):
        """Отправляет оценку в Langfuse.

        Args:
            trace: Трассировка, к которой относится оценка.
            score: Результат оценки.
            metric: Определение метрики, использованной для оценки.
        """
        # Создание оценки в Langfuse
        self.langfuse.create_score(
            trace_id=trace.id,        # ID трассировки
            name=metric["name"],      # Название метрики
            data_type="NUMERIC",      # Тип данных оценки
            value=score.score,        # Числовое значение оценки
            comment=score.reasoning,  # Обоснование оценки
        )

    async def _run_metric_evaluation(self, metric: dict, input: str, output: str) -> ScoreSchema | None:
        """Оценивает одну трассировку по конкретной метрике.

        Args:
            metric: Определение метрики для оценки.
            input: Входные данные для оценки.
            output: Выходные данные для оценки.

        Returns:
            ScoreSchema с результатами оценки или None, если оценка не удалась.
        """
        metric_name = metric["name"]
        # Проверяем, есть ли определение метрики
        if not metric:
            logger.error(f"Метрика {metric_name} не найдена")
            return None
        # Получаем системный промпт для этой метрики
        system_metric_prompt = metric["prompt"]

        # Проверяем, есть ли входные и выходные данные
        if not input or not output:
            logger.error(f"Оценка метрики {metric_name} не удалась", input=input, output=output)
            return None
        # Вызываем API для оценки
        score = await self._call_openai(system_metric_prompt, input, output)
        if score:
            logger.info(f"Оценка метрики {metric_name} завершена успешно", score=score)
        else:
            logger.error(f"Оценка метрики {metric_name} не удалась")
        return score

    async def _call_openai(self, metric_system_prompt: str, input: str, output: str) -> ScoreSchema | None:
        """Вызывает API OpenAI для оценки трассировки.

        Args:
            metric_system_prompt: Системный промпт, определяющий метрику оценки.
            input: Отформатированные входные сообщения.
            output: Отформатированное выходное сообщение.

        Returns:
            ScoreSchema с результатами оценки или None, если вызов API не удался.
        """
        num_retries = 3  # Количество попыток при ошибке API
        for _ in range(num_retries):
            try:
                # Вызов API с использованием structured output (parse)
                response = await self.client.beta.chat.completions.parse(
                    model=settings.EVALUATION_LLM, # Используемая LLM для оценки
                    messages=[
                        {"role": "system", "content": metric_system_prompt}, # Промпт метрики
                        {"role": "user", "content": f"Input: {input}\nGeneration: {output}"}, # Вход и выход
                    ],
                    response_format=ScoreSchema, # Ожидаемый формат ответа
                )
                # Возвращаем распарсенный объект оценки
                return response.choices[0].message.parsed
            except Exception as e:
                SLEEP_TIME = 10 # Время ожидания перед повторной попыткой
                logger.error("Ошибка вызова OpenAI", error=str(e), sleep_time=SLEEP_TIME)
                sleep(SLEEP_TIME) # Ждем перед повторной попыткой
                continue # Переходим к следующей итерации (попытке)
        return None # Если все попытки исчерпаны, возвращаем None

    def __fetch_traces(self) -> list[TraceWithDetails]:
        """Получает трассировки за последние 24 часа без оценок.

        Returns:
            Список трассировок, которые еще не были оценены.
        """
        # Вычисляем дату/время 24 часа назад
        last_24_hours = datetime.now() - timedelta(hours=24)
        try:
            # Запрашиваем трассировки из Langfuse API за последние 24 часа
            traces = self.langfuse.api.trace.list(
                from_timestamp=last_24_hours, # От какой даты
                order_by="timestamp.asc",    # Сортировка по времени (по возрастанию)
                limit=100                    # Ограничение на количество
            ).data
            # Фильтруем трассировки, у которых нет оценок (scores)
            traces_without_scores = [trace for trace in traces if not trace.scores]
            return traces_without_scores
        except Exception as e:
            logger.error("Ошибка получения трассировок", error=str(e))
            return [] # В случае ошибки возвращаем пустой список
