# app/models/__init__.py

# Импорт всех моделей, чтобы SQLAlchemy "увидел" их до старта
from app.models.user.models import User
from app.models.mri.models import Mri
from app.models.clinic.models import Clinic

# Если есть сессии, добавь
try:
    from app.models.session.models import Session
except ImportError:
    Session = None

# Экспорт всех моделей (не обязательно, но удобно)
__all__ = ["User", "Mri", "Clinic", "Session"]

