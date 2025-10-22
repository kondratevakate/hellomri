import asyncio

from telegram.ext import Application

from app.core.config import settings
from app.core.logging import logger
from app.services.telegram_booking import setup_telegram_handlers


async def run_telegram_bot():
    logger.info("telegram_bot_starting")

    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    await setup_telegram_handlers(application)

    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    logger.info("telegram_bot_started")

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("telegram_bot_stopping")
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(run_telegram_bot())
