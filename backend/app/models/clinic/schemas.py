from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SClinic(BaseModel):
    user_id: int = Field(..., description="ID пользователя")
    mri_id: int = Field(..., description="ID снимка МРТ")
    submitted_at: Optional[datetime] = Field(default=None, description="Время подачи")

