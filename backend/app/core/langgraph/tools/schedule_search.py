"""
Инструменты для поиска расписания клиник
"""

from typing import Optional

from langchain_core.tools import tool

from app.core.logging import logger
from app.services.schedule_cache import schedule_cache


@tool
async def search_available_slots(
    day: Optional[str] = None,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    clinic_name: Optional[str] = None,
) -> str:
    """Поиск доступных слотов для записи на МРТ.

    Args:
        day: День недели или дата ('сегодня', 'завтра', 'чт', '23 окт.')
        time_from: Начало временного диапазона (формат '09:00')
        time_to: Конец временного диапазона (формат '18:00')
        clinic_name: Название клиники для фильтрации

    Returns:
        str: JSON с найденными слотами
    """
    import json

    logger.info(
        "search_slots_called",
        day=day,
        time_from=time_from,
        time_to=time_to,
        clinic_name=clinic_name
    )

    try:
        # Получаем актуальное расписание (кэш обновляется автоматически)
        schedule_data = await schedule_cache.get_schedule()
        
        if not schedule_data:
            return json.dumps({
                "error": "Не удалось загрузить расписание. Попробуйте позже.",
                "found": 0
            }, ensure_ascii=False)

        # Поиск по критериям
        results = schedule_cache.search_slots(
            day=day,
            time_from=time_from,
            time_to=time_to,
            clinic_name=clinic_name
        )

        logger.info("slots_found", count=len(results))

        return json.dumps({
            "found": len(results),
            "data_age_minutes": schedule_cache._get_age_minutes(),
            "results": results[:10]  # Ограничиваем до 10 результатов
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error("search_slots_error", error=str(e))
        return json.dumps({
            "error": f"Ошибка поиска: {str(e)}",
            "found": 0
        }, ensure_ascii=False)


@tool
async def get_clinic_info(clinic_name: str) -> str:
    """Получение детальной информации о клинике.

    Args:
        clinic_name: Название клиники

    Returns:
        str: JSON с информацией о клинике
    """
    import json

    logger.info("get_clinic_info_called", clinic_name=clinic_name)

    try:
        schedule_data = await schedule_cache.get_schedule()
        
        if not schedule_data:
            return json.dumps({
                "error": "Расписание недоступно"
            }, ensure_ascii=False)

        # Ищем клинику
        for clinic in schedule_data.get("clinics", []):
            if clinic_name.lower() in clinic.get("clinic_name", "").lower():
                total_slots = sum(
                    len(day.get("times", []))
                    for day in clinic.get("schedule", [])
                )
                
                return json.dumps({
                    "clinic_name": clinic.get("clinic_name"),
                    "doctor_name": clinic.get("doctor_name"),
                    "procedure": clinic.get("procedure"),
                    "price": clinic.get("price"),
                    "address": clinic.get("address"),
                    "coordinates": clinic.get("coordinates"),
                    "total_available_slots": total_slots,
                    "schedule": clinic.get("schedule", [])[:7]  # Первые 7 дней
                }, ensure_ascii=False, indent=2)

        return json.dumps({
            "error": f"Клиника '{clinic_name}' не найдена"
        }, ensure_ascii=False)

    except Exception as e:
        logger.error("get_clinic_info_error", error=str(e))
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
async def get_all_clinics() -> str:
    """Получение списка всех доступных клиник с кратким описанием.

    Returns:
        str: JSON со списком клиник
    """
    import json

    logger.info("get_all_clinics_called")

    try:
        schedule_data = await schedule_cache.get_schedule()
        
        if not schedule_data:
            return json.dumps({
                "error": "Расписание недоступно"
            }, ensure_ascii=False)

        clinics_summary = []
        for clinic in schedule_data.get("clinics", []):
            total_slots = sum(
                len(day.get("times", []))
                for day in clinic.get("schedule", [])
            )
            
            clinics_summary.append({
                "clinic_name": clinic.get("clinic_name"),
                "doctor_name": clinic.get("doctor_name"),
                "price": clinic.get("price"),
                "address": clinic.get("address"),
                "available_slots": total_slots
            })

        return json.dumps({
            "total_clinics": len(clinics_summary),
            "data_age_minutes": schedule_cache._get_age_minutes(),
            "clinics": clinics_summary
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error("get_all_clinics_error", error=str(e))
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
async def refresh_schedule() -> str:
    """Принудительное обновление расписания (если данные устарели).

    Returns:
        str: Статус обновления
    """
    import json

    logger.info("refresh_schedule_called")

    try:
        schedule_data = await schedule_cache.get_schedule(force_refresh=True)
        
        if schedule_data:
            return json.dumps({
                "status": "success",
                "message": "Расписание успешно обновлено",
                "total_clinics": schedule_data.get("total_clinics", 0),
                "timestamp": schedule_data.get("timestamp")
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "status": "error",
                "message": "Не удалось обновить расписание"
            }, ensure_ascii=False)

    except Exception as e:
        logger.error("refresh_schedule_error", error=str(e))
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, ensure_ascii=False)
