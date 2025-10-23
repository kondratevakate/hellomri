import json
from pathlib import Path
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError

from app.core.config import settings
from app.core.logging import logger


class TelegramBookingService:
    """Simplified service for sending booking requests."""

    def __init__(self):
        try:
            self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            self.clinics_file = Path("data/clinic_contacts.json")
            logger.info("telegram_booking_initialized", token_exists=bool(settings.TELEGRAM_BOT_TOKEN))
        except Exception as e:
            logger.error("telegram_booking_init_failed", error=str(e), exc_info=True)
            raise

    def _load_clinics(self) -> dict:
        """Load clinic contact data."""
        try:
            if not self.clinics_file.exists():
                logger.error("clinics_file_not_found", path=str(self.clinics_file))
                return {"clinics": []}
            
            with open(self.clinics_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info("clinics_loaded", count=len(data.get("clinics", [])))
                return data
        except Exception as e:
            logger.error("clinics_load_failed", error=str(e), exc_info=True)
            return {"clinics": []}

    def get_clinic_contact(self, clinic_name: str) -> Optional[dict]:
        """Retrieve clinic contact info by name."""
        clinics = self._load_clinics()
        clinic_name_lower = clinic_name.lower()
        
        for clinic_data in clinics.get("clinics", []):
            if clinic_name_lower in clinic_data.get("name", "").lower():
                logger.info("clinic_found", clinic=clinic_data.get("name"))
                return clinic_data
        
        logger.warning("clinic_not_found", search=clinic_name)
        return None

    async def send_booking_request(
        self,
        user_chat_id: str,
        clinic_name: str,
        date: str,
        time: str,
        patient_name: str,
        patient_phone: str,
        procedure: str = "Pituitary MRI",
    ) -> dict:
        """Send a booking request to the clinic."""
        try:
            logger.info(
                "booking_request_started",
                user_chat_id=user_chat_id,
                clinic=clinic_name,
                date=date,
                time=time
            )

            if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "":
                logger.error("telegram_token_missing")
                return {
                    "status": "error",
                    "message": "Telegram bot token is not configured"
                }

            clinic_contact = self.get_clinic_contact(clinic_name)
            
            if not clinic_contact:
                logger.warning("clinic_contact_not_found", clinic=clinic_name)
                return {
                    "status": "error",
                    "message": f"Clinic '{clinic_name}' not found in contact database"
                }

            clinic_chat_id = clinic_contact.get("telegram_chat_id")
            if not clinic_chat_id:
                logger.warning("telegram_chat_id_missing", clinic=clinic_name)
                return {
                    "status": "error",
                    "message": f"Clinic '{clinic_name}' has no Telegram contact",
                    "phone": clinic_contact.get("phone")
                }

            clinic_message = (
                f"<b>НОВЫЙ ЗАПРОС НА ЗАПИСЬ</b>\n\n"
                f"<b>Процедура:</b> {procedure}\n"
                f"<b>Дата:</b> {date}\n"
                f"<b>Время:</b> {time}\n\n"
                f"<b>Пациент:</b> {patient_name}\n"
                f"<b>Телефон:</b> {patient_phone}\n\n"
                f" Пожалуйста, свяжитесь с пациентом для подтверждения"
            )

            logger.info("sending_to_clinic", chat_id=clinic_chat_id)
            await self.bot.send_message(
                chat_id=clinic_chat_id,
                text=clinic_message,
                parse_mode="HTML",
            )

            logger.info("booking_request_sent_successfully")

            return {
                "status": "success",
                "message": f"Request sent to the registration desk of {clinic_contact['name']}. Please expect a call from the clinic to confirm.",
                "clinic_name": clinic_contact['name'],
                "clinic_phone": clinic_contact.get("phone"),
                "date": date,
                "time": time,
            }

        except TelegramError as e:
            logger.error("telegram_api_error", error=str(e), error_type=type(e).__name__, exc_info=True)
            return {
                "status": "error",
                "message": f"Telegram API error: {str(e)}"
            }
        except Exception as e:
            logger.error("booking_request_failed", error=str(e), exc_info=True)
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}"
            }


try:
    telegram_booking = TelegramBookingService()
except Exception as e:
    logger.error("telegram_booking_service_creation_failed", error=str(e))
    telegram_booking = None



