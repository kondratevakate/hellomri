from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user.models import User
    from app.models.mri.models import Mri


class Clinic(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    mri_id: Mapped[int] = mapped_column(ForeignKey("mri.id"), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="clinics")
    mri: Mapped["Mri"] = relationship(back_populates="clinics")

    def __repr__(self):
        return f"<Clinic id={self.id} user_id={self.user_id} mri_id={self.mri_id} submitted_at={self.submitted_at}>"

