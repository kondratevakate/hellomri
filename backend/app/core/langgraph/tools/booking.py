"""
Tool for booking appointment slots via Telegram
"""

from typing import Optional
from langchain_core.tools import tool
from app.core.logging import logger

@tool
async def book_appointment(
    clinic_name: str,
    date: str,
    time: str,
    patient_name: str,
    patient_phone: str,
    procedure: Optional[str] = "Pituitary MRI",
) -> str:
    """Sends a booking request to the clinic's registration desk via Telegram.

    IMPORTANT: This tool only sends the request to the clinic.
    The registration staff will receive the message and call the patient directly.

    After invoking this tool, respond to the user approximately like this:
    "Great! I've sent your request to [clinic name].
    The registration desk will contact you at [phone] shortly to confirm your appointment."

    Args:
        clinic_name: Name of the clinic (e.g., "MRI Alatau")
        date: Appointment date (e.g., "Oct 22")
        time: Appointment time (e.g., "14:00")
        patient_name: Patient's full name
        patient_phone: Patient's phone number (format: +7XXXXXXXXXX)
        procedure: Name of the procedure (default: "Pituitary MRI")

    Returns:
        str: JSON string with the result of the sending attempt.
        The agent should generate the final user-facing response based on this result.
    """
    import json
    from app.services.telegram_booking import telegram_booking

    logger.info(
        "book_appointment_called",
        clinic=clinic_name,
        date=date,
        time=time,
        patient=patient_name
    )

    # Check if service is initialized
    if telegram_booking is None:
        logger.error("telegram_booking_service_not_initialized")
        return json.dumps({
            "status": "error",
            "message": "Booking service is not initialized. Please check TELEGRAM_BOT_TOKEN settings."
        }, ensure_ascii=False)

    # Normalize phone number
    if not patient_phone.startswith("+"):
        patient_phone = f"+{patient_phone}"

    try:
        result = await telegram_booking.send_booking_request(
            user_chat_id="PLACEHOLDER_CHAT_ID",  # Will be improved later
            clinic_name=clinic_name,
            date=date,
            time=time,
            patient_name=patient_name,
            patient_phone=patient_phone,
            procedure=procedure,
        )

        logger.info("booking_result", status=result.get("status"), message=result.get("message"))

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error("booking_error", error=str(e), exc_info=True)
        return json.dumps({
            "status": "error",
            "message": f"Error: {str(e)}"
        }, ensure_ascii=False)


@tool
def get_clinic_phone(clinic_name: str) -> str:
    """Retrieves the clinic's phone number for direct calling.

    Args:
        clinic_name: Name of the clinic

    Returns:
        str: JSON string with the clinic's contact information
    """
    import json
    from app.services.telegram_booking import telegram_booking

    logger.info("get_clinic_phone_called", clinic=clinic_name)

    try:
        clinic_contact = telegram_booking.get_clinic_contact(clinic_name)

        if clinic_contact:
            return json.dumps({
                "clinic_name": clinic_contact["name"],
                "phone": clinic_contact.get("phone"),
                "telegram": clinic_contact.get("telegram_chat_id"),
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "error": f"Clinic contact for '{clinic_name}' not found"
            }, ensure_ascii=False)

    except Exception as e:
        logger.error("get_clinic_phone_error", error=str(e))
        return json.dumps({"error": str(e)}, ensure_ascii=False)