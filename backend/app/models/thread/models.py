from datetime import datetime, UTC
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime
from app.models.base import Base

class Thread(Base):
    id: Mapped[str] = mapped_column(String, primary_key=True)

