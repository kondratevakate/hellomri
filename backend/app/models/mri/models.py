from typing import TYPE_CHECKING, List
from sqlalchemy import String, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
from app.models.mri.sql_enums import DiagnosisEnum

if TYPE_CHECKING:
    from app.models.user.models import User
    from app.models.clinic.models import Clinic


class Mri(Base):

    id: Mapped[int] = mapped_column(primary_key=True)
    image_path: Mapped[str] = mapped_column(String, nullable=False)
    diagnosis: Mapped[DiagnosisEnum] = mapped_column(Enum(DiagnosisEnum), default=DiagnosisEnum.NORMAL)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="mri")
    clinics: Mapped[List["Clinic"]] = relationship("Clinic", back_populates="mri")

    def __repr__(self):
        return f"<Mri id={self.id} user_id={self.user_id}>"


from app.models.clinic.models import Clinic

