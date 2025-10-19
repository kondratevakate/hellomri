# eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4MzkxZTNjZC02YWMyLTQzZDUtOTJiZS0xMzc1YmJiOTY2ZWYiLCJleHAiOjE3NjMzOTg2NDYsImlhdCI6MTc2MDgwNjY0NiwianRpIjoiODM5MWUzY2QtNmFjMi00M2Q1LTkyYmUtMTM3NWJiYjk2NmVmLTE3NjA4MDY2NDYuMjg0NTk5In0.g8rT-EU7o9xFFz4AwKH4ZYYyhVwrIADcHKPIlkmM_jI
"""This file contains the graph utilities for the application."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import trim_messages as _trim_messages

from app.core.config import settings
from app.schemas import Message


def dump_messages(messages: list[Message]) -> list[dict]:
    """Dump the messages to a list of dictionaries.

    Args:
        messages (list[Message]): The messages to dump.

    Returns:
        list[dict]: The dumped messages.
    """
    return [message.model_dump() for message in messages]


########### При изменении модели на openai удалить и заменить token_counter
import tiktoken

encoding = tiktoken.get_encoding("cl100k_base")
token_counter = lambda x: len(encoding.encode(x.content if hasattr(x, "content") else str(x)))

##############


def prepare_messages(messages: list[Message], llm: BaseChatModel, system_prompt: str) -> list[Message]:
    """Prepare the messages for the LLM.

    Args:
        messages (list[Message]): The messages to prepare.
        llm (BaseChatModel): The LLM to use.
        system_prompt (str): The system prompt to use.

    Returns:
        list[Message]: The prepared messages.
    """
    trimmed_messages = _trim_messages(
        dump_messages(messages),
        strategy="last",
        token_counter=token_counter,    # Заменить на llm. 
        max_tokens=settings.MAX_TOKENS,
        start_on="human",
        include_system=False,
        allow_partial=False,
    )
    return [Message(role="system", content=system_prompt)] + trimmed_messages
