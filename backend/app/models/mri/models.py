from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
from app.models.mri.sql_enums import DiagnosisEnum

if TYPE_CHECKING:
    from app.models.user.models import User

class Mri(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    image_path: Mapped[str] = mapped_column(String, nullable=False)
    diagnosis: Mapped[DiagnosisEnum] = mapped_column(Enum(DiagnosisEnum), default=DiagnosisEnum.NORMAL)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))

    user: Mapped["User"] = relationship(back_populates="mri")

    def __repr__(self):
        return str(self.__dict__)

