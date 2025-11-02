"""Этот файл содержит агент/рабочий процесс LangGraph и взаимодействие с LLM."""

from typing import Any, AsyncGenerator, Dict, Literal, Optional
from urllib.parse import quote_plus # Импортируется, но не используется в данном фрагменте

from asgiref.sync import sync_to_async # Утилита для синхронного вызова асинхронного кода
from langchain_core.messages import ( # Классы сообщений LangChain
    BaseMessage, # Базовый класс для всех сообщений
    ToolMessage, # Сообщение с результатом инструмента
    convert_to_openai_messages, # Функция преобразования сообщений в формат OpenAI
)
from langchain_openai import ChatOpenAI # Модель чата OpenAI (или совместимая)
from langfuse.langchain import CallbackHandler # Обработчик для интеграции с Langfuse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver # Асинхронный чекпоинтер для PostgreSQL
from langgraph.graph import ( # Основные компоненты графа LangGraph
    END, # Узел окончания
    StateGraph, # Класс для построения графа состояний
)
from langgraph.graph.state import CompiledStateGraph # Скомпилированный граф состояний
from langgraph.types import StateSnapshot # Снимок состояния графа
from openai import OpenAIError # Класс ошибок OpenAI
from psycopg_pool import AsyncConnectionPool # Асинхронный пул соединений к PostgreSQL

from app.core.config import Environment, settings # Настройки приложения и перечисление Environment
from app.core.langgraph.tools import tools # Импорт инструментов LangGraph
from app.core.logging import logger # Логгер приложения
from app.core.metrics import llm_inference_duration_seconds # Метрика времени выполнения LLM
from app.core.prompts import SYSTEM_PROMPT # Системный промпт
from app.schemas import ( # Pydantic схемы
    GraphState, # Состояние графа
    Message, # Схема сообщения
)
from app.utils import ( # Вспомогательные функции
    dump_messages, # Функция сериализации сообщений
    prepare_messages, # Функция подготовки сообщений для LLM
)


class LangGraphAgent:
    """Управляет агентом/рабочим процессом LangGraph и взаимодействием с LLM.

    Этот класс отвечает за создание и управление рабочим процессом LangGraph,
    включая взаимодействие с LLM, подключения к базе данных и обработку ответов.
    """

    def __init__(self):
        """Инициализирует LangGraph Agent с необходимыми компонентами."""
        # Использовать модель LLM, специфичную для среды
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL, # Модель LLM из настроек
            temperature=settings.DEFAULT_LLM_TEMPERATURE, # Температура из настроек
            api_key=settings.LLM_API_KEY, # API ключ из настроек
            max_tokens=settings.MAX_TOKENS, # Максимальное количество токенов
            base_url=settings.EVALUATION_BASE_URL,  # Базовый URL для API (например, для DeepSeek)
            **self._get_model_kwargs(), # Дополнительные аргументы модели, специфичные для среды
        ).bind_tools(tools) # Привязать инструменты к LLM
        # Создать словарь для быстрого доступа к инструментам по имени
        self.tools_by_name = {tool.name: tool for tool in tools}
        # Асинхронный пул соединений к PostgreSQL (инициализируется позже)
        self._connection_pool: Optional[AsyncConnectionPool] = None
        # Скомпилированный граф LangGraph (инициализируется позже)
        self._graph: Optional[CompiledStateGraph] = None

        # Логировать инициализацию LLM
        logger.info("llm_initialized", model=settings.LLM_MODEL, environment=settings.ENVIRONMENT.value)

    def _get_model_kwargs(self) -> Dict[str, Any]:
        """Получить аргументы модели, специфичные для среды.

        Returns:
            Dict[str, Any]: Дополнительные аргументы модели, основанные на среде
        """
        model_kwargs = {}

        # Разработка - можно использовать более низкие скорости для экономии затрат
        if settings.ENVIRONMENT == Environment.DEVELOPMENT:
            model_kwargs["top_p"] = 0.8

        # Продакшн - использовать более качественные настройки
        elif settings.ENVIRONMENT == Environment.PRODUCTION:
            model_kwargs["top_p"] = 0.95
            model_kwargs["presence_penalty"] = 0.1
            model_kwargs["frequency_penalty"] = 0.1

        return model_kwargs

    async def _get_connection_pool(self) -> AsyncConnectionPool:
        """Получить пул соединений с PostgreSQL, используя настройки, специфичные для среды.

        Returns:
            AsyncConnectionPool: Пул соединений для базы данных PostgreSQL.
        """

        if self._connection_pool is None: # Инициализировать пул, если он еще не создан
            try:
                # connection_url = (f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@"
                #                   f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")

                # ЖЕСТКО ЗАКОДИРОВАННЫЙ URL подключения. ИСПОЛЬЗУЕТ ЛОКАЛЬНЫЙ ХОСТ, А НЕ ИМЯ СЕРВИСА DOCKER!
                connection_url = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"

                max_size = settings.POSTGRES_POOL_SIZE # Размер пула из настроек
                self._connection_pool = AsyncConnectionPool( # Создать асинхронный пул
                    connection_url,
                    open=False, # Не открывать соединение сразу
                    max_size=max_size,
                    kwargs={ # Дополнительные аргументы для соединений psycopg
                        "autocommit": True, # Автоматически фиксировать транзакции
                        "connect_timeout": 5, # Таймаут подключения
                        "prepare_threshold": None, # Отключить подготовленные операторы
                    },
                )
                await self._connection_pool.open() # Асинхронно открыть пул
                # Логировать успешное создание пула
                logger.info("connection_pool_created", max_size=max_size, environment=settings.ENVIRONMENT.value)
            except Exception as e: # Обработать ошибки при создании пула
                logger.error("connection_pool_creation_failed", error=str(e), environment=settings.ENVIRONMENT.value)
                # В продакшн среде, возможно, стоит изящно понизить функциональность
                if settings.ENVIRONMENT == Environment.PRODUCTION:
                    logger.warning("continuing_without_connection_pool", environment=settings.ENVIRONMENT.value)
                    return None
                raise e # В других средах (например, разработка) пробросить ошибку
        return self._connection_pool

    async def _chat(self, state: GraphState) -> dict:
        """Обрабатывает состояние чата и генерирует ответ.

        Args:
            state (GraphState): Текущее состояние разговора.

        Returns:
            dict: Обновленное состояние с новыми сообщениями.
        """
        # Подготовить сообщения для LLM, включая системный промпт
        messages = prepare_messages(state.messages, self.llm, SYSTEM_PROMPT)

        llm_calls_num = 0 # Счетчик вызовов LLM

        # Настроить количество попыток повтора в зависимости от среды
        max_retries = settings.MAX_LLM_CALL_RETRIES

        for attempt in range(max_retries): # Цикл для повторных попыток вызова LLM
            try:
                # Измерить время выполнения LLM с помощью метрики
                with llm_inference_duration_seconds.labels(model=self.llm.model_name).time():
                    # Асинхронно вызвать LLM с подготовленными сообщениями
                    generated_state = {"messages": [await self.llm.ainvoke(dump_messages(messages))]}
                # Логировать успешный ответ LLM
                logger.info(
                    "llm_response_generated",
                    session_id=state.session_id,
                    llm_calls_num=llm_calls_num + 1,
                    model=settings.LLM_MODEL,
                    environment=settings.ENVIRONMENT.value,
                )
                return generated_state # Вернуть сгенерированное состояние
            except OpenAIError as e: # Обработать ошибки OpenAI
                logger.error(
                    "llm_call_failed", # Логировать ошибку вызова LLM
                    llm_calls_num=llm_calls_num,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    error=str(e),
                    environment=settings.ENVIRONMENT.value,
                )
                llm_calls_num += 1 # Увеличить счетчик вызовов

                # В продакшн среде, возможно, использовать резервную модель
                if settings.ENVIRONMENT == Environment.PRODUCTION and attempt == max_retries - 2:
                    fallback_model = "deepseek-chat"  # Резервная модель
                    logger.warning(
                        "using_fallback_model", model=fallback_model, environment=settings.ENVIRONMENT.value
                    )
                    self.llm.model_name = fallback_model # Изменить модель LLM на резервную

                continue # Продолжить цикл, чтобы сделать следующую попытку

        # Если все попытки исчерпаны, вызвать исключение
        raise Exception(f"Failed to get a response from the LLM after {max_retries} attempts")

    # Определяем наш узел инструмента
    async def _tool_call(self, state: GraphState) -> GraphState:
        """Обрабатывает вызовы инструментов из последнего сообщения.

        Args:
            state: Текущее состояние агента, содержащее сообщения и вызовы инструментов.

        Returns:
            Dict с обновленными сообщениями, содержащими ответы инструментов.
        """
        outputs = [] # Список для хранения результатов инструментов
        # Пройтись по всем вызовам инструментов в последнем сообщении
        for tool_call in state.messages[-1].tool_calls:
            # Асинхронно вызвать инструмент с указанными аргументами
            tool_result = await self.tools_by_name[tool_call["name"]].ainvoke(tool_call["args"])
            # Добавить результат инструмента в список outputs как ToolMessage
            outputs.append(
                ToolMessage(
                    content=tool_result, # Результат инструмента
                    name=tool_call["name"], # Имя инструмента
                    tool_call_id=tool_call["id"], # ID вызова инструмента
                )
            )
        return {"messages": outputs} # Вернуть обновленные сообщения

    def _should_continue(self, state: GraphState) -> Literal["end", "continue"]:
        """Определяет, должен ли агент продолжать работу или завершить её на основе последнего сообщения.

        Args:
            state: Текущее состояние агента, содержащее сообщения.

        Returns:
            Literal["end", "continue"]: "end", если нет вызовов функций, "continue" в противном случае.
        """
        messages = state.messages # Получить список сообщений
        last_message = messages[-1] # Получить последнее сообщение
        # Если нет вызовов инструментов, завершить
        if not last_message.tool_calls:
            return "end"
        # В противном случае, если есть вызовы, продолжить
        else:
            return "continue"

    async def create_graph(self) -> Optional[CompiledStateGraph]:
        """Создает и настраивает рабочий процесс LangGraph.

        Returns:
            Optional[CompiledStateGraph]: Настроенный экземпляр LangGraph или None, если инициализация не удалась
        """
        if self._graph is None: # Создать граф, если он еще не создан
            try:
                graph_builder = StateGraph(GraphState) # Создать билдер графа
                # Добавить узлы: один для чата, другой для вызова инструментов
                graph_builder.add_node("chat", self._chat)
                graph_builder.add_node("tool_call", self._tool_call)
                # Добавить условные ребра от узла 'chat' к 'tool_call' или 'END'
                graph_builder.add_conditional_edges(
                    "chat",
                    self._should_continue, # Функция, определяющая направление
                    {"continue": "tool_call", "end": END}, # Карта направлений
                )
                # Добавить ребро от 'tool_call' обратно к 'chat'
                graph_builder.add_edge("tool_call", "chat")
                graph_builder.set_entry_point("chat") # Установить начальную точку
                graph_builder.set_finish_point("chat") # Установить точку завершения

                # Получить пул соединений (может быть None в продакшне, если БД недоступна)
                connection_pool = await self._get_connection_pool()
                if connection_pool: # Если пул создан успешно
                    # Создать чекпоинтер, используя пул соединений
                    checkpointer = AsyncPostgresSaver(connection_pool)
                    await checkpointer.setup() # Настроить таблицы в БД для чекпоинтов
                else:
                    # В продакшн, продолжить без чекпоинтера, если нужно
                    checkpointer = None
                    if settings.ENVIRONMENT != Environment.PRODUCTION:
                        raise Exception("Connection pool initialization failed") # В dev бросить ошибку

                # Скомпилировать граф с чекпоинтером и именем
                self._graph = graph_builder.compile(
                    checkpointer=checkpointer, name=f"{settings.PROJECT_NAME} Agent ({settings.ENVIRONMENT.value})"
                )

                # Логировать успешное создание графа
                logger.info(
                    "graph_created",
                    graph_name=f"{settings.PROJECT_NAME} Agent",
                    environment=settings.ENVIRONMENT.value,
                    has_checkpointer=checkpointer is not None, # Указывает, был ли использован чекпоинтер
                )
            except Exception as e: # Обработать ошибки при создании графа
                logger.error("graph_creation_failed", error=str(e), environment=settings.ENVIRONMENT.value)
                # В продакшн, не стоит падать приложению
                if settings.ENVIRONMENT == Environment.PRODUCTION:
                    logger.warning("continuing_without_graph") # Логировать предупреждение
                    return None # Вернуть None
                raise e # В других средах пробросить ошибку

        return self._graph # Вернуть скомпилированный граф

    async def get_response(
        self,
        messages: list[Message],
        session_id: str,
        user_id: Optional[str] = None,
    ) -> list[dict]:
        """Получить ответ от LLM.

        Args:
            messages (list[Message]): Сообщения для отправки LLM.
            session_id (str): ID сессии для отслеживания в Langfuse.
            user_id (Optional[str]): ID пользователя для отслеживания в Langfuse.

        Returns:
            list[dict]: Ответ от LLM.
        """
        if self._graph is None: # Создать граф, если он еще не создан
            self._graph = await self.create_graph()
        # Конфигурация для вызова графа
        config = {
            "configurable": {"thread_id": session_id}, # ID потока для чекпоинтера
            "callbacks": [CallbackHandler()], # Обработчик для Langfuse
            "metadata": { # Метаданные для отслеживания
                "user_id": user_id,
                "session_id": session_id,
                "environment": settings.ENVIRONMENT.value,
                "debug": False,
            },
        }
        try:
            # Асинхронно вызвать граф с начальным состоянием
            response = await self._graph.ainvoke(
                {"messages": dump_messages(messages), "session_id": session_id}, config
            )
            # Обработать и вернуть сообщения из ответа
            return self.__process_messages(response["messages"])
        except Exception as e: # Обработать ошибки при получении ответа
            logger.error(f"Error getting response: {str(e)}")
            raise e

    async def get_stream_response(
        self, messages: list[Message], session_id: str, user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Получить потоковый ответ от LLM.

        Args:
            messages (list[Message]): Сообщения для отправки LLM.
            session_id (str): ID сессии для разговора.
            user_id (Optional[str]): ID пользователя для разговора.

        Yields:
            str: Токены ответа LLM.
        """
        # Конфигурация для потокового вызова графа
        config = {
            "configurable": {"thread_id": session_id}, # ID потока
            "callbacks": [ # Обработчики для Langfuse
                CallbackHandler(
                    environment=settings.ENVIRONMENT.value, debug=False, user_id=user_id, session_id=session_id
                )
            ],
        }
        if self._graph is None: # Создать граф, если он еще не создан
            self._graph = await self.create_graph()

        try:
            # Асинхронно перебирать токены из ответа графа
            async for token, _ in self._graph.astream(
                {"messages": dump_messages(messages), "session_id": session_id}, config, stream_mode="messages"
            ):
                try:
                    yield token.content # Возвращать содержимое токена
                except Exception as token_error: # Обработать ошибки при обработке токена
                    logger.error("Error processing token", error=str(token_error), session_id=session_id)
                    # Продолжить с следующего токена, даже если текущий не удался
                    continue
        except Exception as stream_error: # Обработать ошибки в потоковой передаче
            logger.error("Error in stream processing", error=str(stream_error), session_id=session_id)
            raise stream_error

    async def get_chat_history(self, session_id: str) -> list[Message]:
        """Получить историю чата для заданного ID потока.

        Args:
            session_id (str): ID сессии для разговора.

        Returns:
            list[Message]: История чата.
        """
        if self._graph is None: # Создать граф, если он еще не создан
            self._graph = await self.create_graph()

        # Получить снимок состояния графа для конкретного потока (синхронно, обернуто)
        state: StateSnapshot = await sync_to_async(self._graph.get_state)(
            config={"configurable": {"thread_id": session_id}}
        )
        # Обработать и вернуть сообщения из снимка состояния
        return self.__process_messages(state.values["messages"]) if state.values else []

    def __process_messages(self, messages: list[BaseMessage]) -> list[Message]:
        # Преобразовать сообщения LangGraph в формат OpenAI
        openai_style_messages = convert_to_openai_messages(messages)
        # Оставить только сообщения ассистента и пользователя, у которых есть содержимое
        return [
            Message(**message) # Создать экземпляр Pydantic Message
            for message in openai_style_messages
            if message["role"] in ["assistant", "user"] and message["content"] # Фильтр
        ]

    async def clear_chat_history(self, session_id: str) -> None:
        """Очистить всю историю чата для заданного ID потока.

        Args:
            session_id: ID сессии, для которой нужно очистить историю.

        Raises:
            Exception: Если произошла ошибка при очистке истории чата.
        """
        try:
            # Убедиться, что пул инициализирован в текущем цикле событий
            conn_pool = await self._get_connection_pool()

            # Использовать новое соединение для этой конкретной операции
            async with conn_pool.connection() as conn:
                # Пройтись по таблицам, определенным в настройках для чекпоинтов
                for table in settings.CHECKPOINT_TABLES:
                    try:
                        # Выполнить DELETE для конкретного thread_id
                        await conn.execute(f"DELETE FROM {table} WHERE thread_id = %s", (session_id,))
                        logger.info(f"Cleared {table} for session {session_id}") # Логировать успех
                    except Exception as e: # Обработать ошибки при очистке конкретной таблицы
                        logger.error(f"Error clearing {table}", error=str(e))
                        raise # Пробросить ошибку, чтобы прервать очистку

        except Exception as e: # Обработать ошибки при очистке всей истории
            logger.error("Failed to clear chat history", error=str(e))
            raise
