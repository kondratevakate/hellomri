from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


from typing import Optional
from pydantic import BaseModel, Field

class SUser(BaseModel):
    email: Optional[str] = Field(None, description="Электронная почта")
    password: Optional[str] = Field(None, description="Пароль")  

