import re
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


from typing import Optional
from pydantic import BaseModel, Field

class SUser(BaseModel):
    email: Optional[str] = Field(None, description="Электронная почта")
    # hashed_password или password — в зависимости от того, что ты хочешь использовать
    password: Optional[str] = Field(None, description="Пароль")  # или hashed_password, если уже зашифрован
    # id: Optional[int] = Field(None, description="ID пользователя")  # если нужно

    # Убираем валидатор телефона, т.к. поле phone_number убрано