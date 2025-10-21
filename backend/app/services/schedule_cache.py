"""
Кэширующий сервис для расписания клиник с автоматическим обновлением
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from app.core.config import settings
from app.core.logging import logger


class ScheduleCache:
    """Singleton кэш расписания с автоматическим обновлением."""

    _instance: Optional['ScheduleCache'] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.url = "https://doq.kz/doctors/almaty/mrt-gipofiza"
        self.cache_duration = timedelta(minutes=15)
        self.cache_file = Path("data/clinic_schedule_cache.json")
        
        self._data: Optional[dict[str, Any]] = None
        self._last_update: Optional[datetime] = None
        self._is_updating = False
        
        self._initialized = True
        logger.info("schedule_cache_initialized")

    @property
    def is_stale(self) -> bool:
        """Проверка устаревания кэша."""
        if self._last_update is None:
            return True
        return datetime.utcnow() - self._last_update > self.cache_duration

    async def get_schedule(self, force_refresh: bool = False) -> Optional[dict[str, Any]]:
        """Получение расписания с автоматическим обновлением.

        Args:
            force_refresh: Принудительное обновление кэша

        Returns:
            dict: Данные расписания или None при ошибке
        """
        # Если кэш свежий и не требуется принудительное обновление
        if not force_refresh and not self.is_stale and self._data is not None:
            logger.debug("schedule_cache_hit", age_minutes=self._get_age_minutes())
            return self._data

        # Если уже идёт обновление, ждём его завершения
        if self._is_updating:
            logger.debug("schedule_update_in_progress_waiting")
            await self._wait_for_update()
            return self._data

        # Запускаем обновление
        async with self._lock:
            # Двойная проверка после получения лока
            if not force_refresh and not self.is_stale and self._data is not None:
                return self._data

            self._is_updating = True
            try:
                logger.info("schedule_update_started", force_refresh=force_refresh)
                new_data = await self._fetch_schedule()
                
                if new_data:
                    self._data = new_data
                    self._last_update = datetime.utcnow()
                    await self._save_to_file()
                    logger.info(
                        "schedule_updated",
                        clinics=new_data.get("total_clinics", 0),
                        slots=self._count_slots(new_data)
                    )
                else:
                    logger.warning("schedule_update_failed_keeping_old")
                    
                return self._data

            finally:
                self._is_updating = False

    async def _wait_for_update(self, timeout: int = 60) -> None:
        """Ожидание завершения текущего обновления."""
        start = datetime.utcnow()
        while self._is_updating:
            if (datetime.utcnow() - start).seconds > timeout:
                logger.warning("update_wait_timeout")
                break
            await asyncio.sleep(0.5)

    async def _fetch_schedule(self) -> Optional[dict[str, Any]]:
        """Парсинг расписания со страницы."""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                try:
                    await page.goto(self.url, timeout=60000)
                    await page.wait_for_load_state("networkidle")
                except PlaywrightTimeoutError:
                    logger.error("page_load_timeout")
                    await browser.close()
                    return None

                clinic_cards = await page.query_selector_all("div.css-49aokf")
                logger.debug("clinic_cards_found", count=len(clinic_cards))

                all_clinics = []

                for idx, card in enumerate(clinic_cards):
                    # Раскрываем расписание
                    try:
                        show_more_btn = await card.query_selector('button[data-selector=""].css-81xnd3, button.css-81xnd3')
                        if show_more_btn:
                            btn_text = await show_more_btn.inner_text()
                            if "Показать" in btn_text or "показать" in btn_text:
                                await show_more_btn.click()
                                await asyncio.sleep(0.3)
                    except Exception:
                        pass

                    try:
                        clinic_data = {}

                        # Парсинг данных клиники
                        doctor_el = await card.query_selector("h2.profile-info-text-0 a")
                        if doctor_el:
                            clinic_data["doctor_name"] = (await doctor_el.inner_text()).strip().replace('\n', ' ')

                        procedure_el = await card.query_selector("div.css-jq4y5l")
                        if procedure_el:
                            clinic_data["procedure"] = (await procedure_el.inner_text()).strip()

                        price_el = await card.query_selector("div.css-g26lc2, div.css-g261c2")
                        if price_el:
                            clinic_data["price"] = (await price_el.inner_text()).strip()

                        clinic_name_el = await card.query_selector("a.css-10hvubl, a.css-1unrqcp")
                        if clinic_name_el:
                            clinic_data["clinic_name"] = (await clinic_name_el.inner_text()).strip()

                        address_el = await card.query_selector('div[itemprop="address"]')
                        if address_el:
                            clinic_data["address"] = (await address_el.inner_text()).strip()

                        # Координаты
                        map_el = await card.query_selector('div[data-selector="onMapLink"] a, a[href*="/map?lat="]')
                        if map_el:
                            href = await map_el.get_attribute("href")
                            if href:
                                import re
                                lat_m = re.search(r'lat=([\d.]+)', href)
                                lng_m = re.search(r'lng=([\d.]+)', href)
                                if lat_m and lng_m:
                                    clinic_data["coordinates"] = {
                                        "lat": float(lat_m.group(1)),
                                        "lng": float(lng_m.group(1))
                                    }

                        # Расписание
                        schedule_days = await card.query_selector_all("div.css-xemt3x")
                        schedule = []

                        for day_block in schedule_days:
                            day_info = {}
                            
                            date_header = await day_block.query_selector("div.css-158h1ju")
                            if date_header:
                                date_divs = await date_header.query_selector_all("div")
                                if len(date_divs) >= 2:
                                    day_info["day"] = (await date_divs[0].inner_text()).strip()
                                    day_info["date"] = (await date_divs[1].inner_text()).strip()

                            time_btns = await day_block.query_selector_all("button.css-1ui2caq")
                            times = [
                                (await btn.inner_text()).strip()
                                for btn in time_btns
                                if await btn.inner_text()
                            ]
                            day_info["times"] = times
                            if times:
                                schedule.append(day_info)

                        clinic_data["schedule"] = schedule
                        all_clinics.append(clinic_data)

                    except Exception as e:
                        logger.error("clinic_parse_error", idx=idx, error=str(e))
                        continue

                await browser.close()

                return {
                    "timestamp": datetime.utcnow().isoformat(),
                    "url": self.url,
                    "total_clinics": len(all_clinics),
                    "clinics": all_clinics
                }

        except Exception as e:
            logger.error("schedule_fetch_failed", error=str(e), exc_info=True)
            return None

    async def _save_to_file(self) -> None:
        """Сохранение кэша в файл."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("cache_file_save_failed", error=str(e))

    def _get_age_minutes(self) -> int:
        """Возраст кэша в минутах."""
        if self._last_update is None:
            return 9999
        return int((datetime.utcnow() - self._last_update).total_seconds() / 60)

    def _count_slots(self, data: dict[str, Any]) -> int:
        """Подсчёт общего количества слотов."""
        total = 0
        for clinic in data.get("clinics", []):
            for day in clinic.get("schedule", []):
                total += len(day.get("times", []))
        return total

    def search_slots(
        self,
        day: Optional[str] = None,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        clinic_name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Поиск слотов по критериям."""
        if self._data is None:
            return []

        results = []

        for clinic in self._data.get("clinics", []):
            if clinic_name and clinic_name.lower() not in clinic.get("clinic_name", "").lower():
                continue

            for day_schedule in clinic.get("schedule", []):
                if day:
                    day_lower = day.lower()
                    if day_lower not in day_schedule.get("day", "").lower() and \
                       day_lower not in day_schedule.get("date", "").lower():
                        continue

                times = day_schedule.get("times", [])
                if time_from or time_to:
                    times = [
                        t for t in times
                        if (not time_from or t >= time_from) and (not time_to or t <= time_to)
                    ]

                if times:
                    results.append({
                        "clinic_name": clinic.get("clinic_name"),
                        "doctor_name": clinic.get("doctor_name"),
                        "address": clinic.get("address"),
                        "price": clinic.get("price"),
                        "coordinates": clinic.get("coordinates"),
                        "day": day_schedule.get("day"),
                        "date": day_schedule.get("date"),
                        "available_times": times,
                    })

        return results


# Глобальный singleton
schedule_cache = ScheduleCache()
