import os
import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# === Log directory setup ===
LOG_DIR = "src/mastercard_solution_tech_stack_agent/logs"
os.makedirs(LOG_DIR, exist_ok=True)  # Ensure the logs directory exists

# === Log file paths ===
LOG_FILES = {
    "info": os.path.join(LOG_DIR, "info.log"),
    "warning": os.path.join(LOG_DIR, "warning.log"),
    "error": os.path.join(LOG_DIR, "error.log"),
}


T = TypeVar("T")

class UserSession(BaseModel):
    session_id: str
    user_id: int
    conversation_summary: Optional[str] = None
    recommended_stack: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "session_id": "session123",
                "user_id": "user456",
                "conversation_summary": "A summary of the conversation.",
                "recommended_stack": "Python, FastAPI, React",
                "created_at": "2024-01-01T12:00:00",
            }
        }

class PaginationMetadata(BaseModel):
    total: int
    limit: int
    offset: int
    current_page: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    metadata: PaginationMetadata
    results: List[T]


# Token Schema
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Admin Schemas
class Admin(BaseModel):
    id: int
    email: EmailStr
    permissions: Optional[List[str]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str


# Define a Pydantic schema for the request body
class VerificationRequest(BaseModel):
    email: EmailStr
    otp: str


class UserCreate(UserBase):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    profile_picture_url: Optional[str] = None
    password: str = Field(
        ..., min_length=8, description="Password must be at least 8 characters long."
    )

    @field_validator("password")
    def password_strength(cls, v):
        """Validate password strength with uppercase, lowercase, number, and special character."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>_]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserVerify(BaseModel):
    email: EmailStr
    otp: str


class UserProfileBase(BaseModel):
    id: int
    email: EmailStr
    first_name: str
    last_name: str
    is_verified: bool

    is_admin: bool
    is_expert: bool
    # Add other fields relevant to the profile

    class Config:
        from_attributes = True


class UserProfileResponse(BaseModel):
    id: int
    email: EmailStr
    first_name: str
    last_name: str
    profile_picture_url: Optional[str] = None
    is_active: bool
    is_verified: bool
    is_admin: bool
    is_super_admin: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=obj.id,
            email=obj.email,
            first_name=obj.first_name,
            last_name=obj.last_name,
            profile_picture_url=getattr(obj, "profile_picture_url", None),
            nationality=getattr(obj, "nationality", None),
            is_active=obj.is_active,
            is_verified=obj.is_verified,
            is_admin=obj.is_admin,
            is_super_admin=obj.is_super_admin,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )

    class Config:
        from_attributes = True


class PasswordResetConfirmation(BaseModel):
    email: Optional[EmailStr] = None
    otp: str
    new_password: str

    @field_validator("new_password")
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>_]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class PasswordUpdateSchema(BaseModel):
    new_password: str = Field(
        ..., min_length=8, description="The new password for the user"
    )
    confirm_new_password: str = Field(
        ..., description="Confirmation of the new password"
    )

    @model_validator(mode="after")
    def validate_passwords(cls, values):
        new_password = values.new_password
        confirm_new_password = values.confirm_new_password

        if new_password != confirm_new_password:
            raise ValueError("Passwords do not match")

        # Additional password strength checks
        if not any(char.isupper() for char in new_password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in new_password):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(char.isdigit() for char in new_password):
            raise ValueError("Password must contain at least one number")
        if not any(char in '!@#$%^&*(),.?":{}|<>_' for char in new_password):
            raise ValueError("Password must contain at least one special character")

        return values


# Admin Schemas
class AdminDetails(BaseModel):
    id: int
    email: EmailStr
    first_name: str
    last_name: str

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


# Admin Login Schema
class Login(BaseModel):
    email: EmailStr
    password: str


class ChangeSuperAdminPassword(BaseModel):
    current_password: str
    new_password: str


# Admin Credentials Update Schema
class UpdateAdminCredentials(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None

    class Config:
        from_attributes = True


class ConversationSummary(BaseModel):
    summary: str


class AIMessageResponse(BaseModel):
    content: str
    id: Optional[str] = None
    usage_metadata: Optional[Dict[str, Any]] = None
    response_metadata: Optional[Dict[str, Any]] = None
    additional_kwargs: Optional[Dict[str, Any]] = None


class Chat_Message(BaseModel):
    id: Optional[Union[str, int]] = None
    session_id: str  # ✅ Add this
    message: str

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "id": "18",
                "session_id": "abc123",
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


class ProjectCategory(str, Enum):
    health = "Health"
    agriculture = "Agriculture"
    education = "Education"
    finance = "Finance"
    clean_energy = "Clean Energy"
    others = "Others"


class ProjectDescriptionRequest(BaseModel):
    session_id: str = Field(..., description="Session ID for tracking")
    project_title: str = Field(..., description="Title of the project")
    project_description: str = Field(..., description="Description of the project")
    category: ProjectCategory = Field(..., description="Predefined or custom category")
    custom_category: Optional[str] = Field(
        None, description="If 'Others' is selected, specify a custom category"
    )


class ProjectDescriptionResponse(BaseModel):
    message: str
    data: ProjectDescriptionRequest
