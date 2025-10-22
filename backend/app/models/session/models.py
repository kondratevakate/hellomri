"""This file contains the session model for the application."""

from typing import TYPE_CHECKING
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlmodel import Field
from sqlalchemy import String, ForeignKey

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user.models import User


class Session(Base):
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    name: Mapped[str] = mapped_column(String, default="")

    user: Mapped["User"] = relationship(back_populates="sessions")

