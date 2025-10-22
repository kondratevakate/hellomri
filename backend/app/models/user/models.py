from typing import TYPE_CHECKING, List
import bcrypt
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.session.models import Session
    from app.models.mri.models import Mri
    from app.models.clinic.models import Clinic


class User(Base):

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)

    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="user")
    mri: Mapped[List["Mri"]] = relationship("Mri", back_populates="user")
    clinics: Mapped[List["Clinic"]] = relationship("Clinic", back_populates="user")

    def verify_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), self.hashed_password.encode("utf-8"))

    @staticmethod
    def hash_password(password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

