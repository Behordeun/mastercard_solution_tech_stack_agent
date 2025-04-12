from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel, EmailStr, Field


class Chat_Message(BaseModel):
    id: Optional[Union[str, int]] = None
    roomId: str  # ✅ Add this
    message: str

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "id": "18",
                "roomId": "abc123",
                "message": "Hello",
            }
        }


class Chat_Response(BaseModel):
    id: Optional[Union[str, int]] = Field(default=None)
    message: str

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "message": "Hello, how can I assist you?",
            }
        }


class User(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    email: EmailStr
    password: str

    class Config:
        from_attributes = True


class UserVerify(BaseModel):
    email: EmailStr
    password: str

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    email: Optional[EmailStr]
    password: Optional[str]
    is_active: Optional[bool]

    class Config:
        from_attributes = True


class UserProfileBase(BaseModel):
    user_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    bio: Optional[str]
    profile_picture_url: Optional[str]

    class Config:
        from_attributes = True


class UserProfileResponse(UserProfileBase):
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class Admin(BaseModel):
    id: int
    email: EmailStr
    is_superuser: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class AdminCreate(BaseModel):
    email: EmailStr
    password: str
    is_superuser: bool = False

    class Config:
        from_attributes = True


class AdminUpdate(BaseModel):
    email: Optional[EmailStr]
    password: Optional[str]
    is_superuser: Optional[bool]

    class Config:
        from_attributes = True


class AdminResponse(BaseModel):
    id: int
    email: EmailStr
    is_superuser: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Account deletion confirmation schemas
class ConfirmAccountDeletion(BaseModel):
    email: EmailStr
    otp: str


# Account recovery schemas
class RecoverAccountRequest(BaseModel):
    email: EmailStr
    otp: str
