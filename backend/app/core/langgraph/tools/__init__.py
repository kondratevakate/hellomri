"""
Регистрация всех инструментов для LangGraph агента
"""

from app.core.langgraph.tools.schedule_search import (
    search_available_slots,
    get_clinic_info,
    get_all_clinics,
    refresh_schedule,
)

# Список всех доступных инструментов
tools = [
    search_available_slots,
    get_clinic_info,
    get_all_clinics,
    refresh_schedule,
]

__all__ = [
    "tools",
    "search_available_slots",
    "get_clinic_info",
    "get_all_clinics",
    "refresh_schedule",
]
