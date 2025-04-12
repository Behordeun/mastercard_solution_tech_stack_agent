import logging
import re
import secrets
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from pydantic_core.core_schema import ValidationInfo
from sqlalchemy.ext.declarative import declarative_base

from src.mastercard_solution_tech_stack_agent.utilities.countries_utils import (
    countries_data,
)

Base = declarative_base()

logger = logging.getLogger(__name__)

T = TypeVar("T")


# Dynamically create a Literal type for valid country names from countries_data
CountryNameLiteral = Literal[
    tuple(country.name for country in countries_data.countries)
]

# Create a mapping of country names to country codes for quick lookup
country_code_mapping = {
    country.name: country.country_code for country in countries_data.countries
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


# Define Enums
class Gender(str, Enum):
    male = "Male"
    female = "Female"
    other = "Other"


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
    username: str


# Define a Pydantic schema for the request body
class VerificationRequest(BaseModel):
    email: EmailStr
    otp: str


class UserCreate(UserBase):
    username: str
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    profile_picture: Optional[str] = None
    bio: Optional[str] = None
    linkedin: Optional[str] = None
    twitter: Optional[str] = None
    nationality: Optional[str] = None
    phone_number: Optional[str] = None
    gender: Optional[Gender] = None
    password: str = Field(
        ..., min_length=8, description="Password must be at least 8 characters long."
    )
    confirm_password: str

    @field_validator("username")
    def validate_username(cls, v):
        """Ensure the username starts with a letter and contains only letters, numbers, or underscores."""
        if not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", v):
            raise ValueError(
                "Invalid username. It must start with a letter and contain only alphabets, numbers, or underscores."
            )
        return v.strip()

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

    @field_validator("confirm_password")
    def passwords_match(cls, v, info: ValidationInfo):
        """Ensure password and confirm password match."""
        if v != info.data.get("password"):
            raise ValueError("Passwords do not match.")
        return v
        return v


class UserVerify(BaseModel):
    email: EmailStr
    otp: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture: Optional[str] = None
    # Custom Literal for country names
    nationality: Optional[CountryNameLiteral] = None
    linkedin: Optional[str] = None
    twitter: Optional[str] = None
    phone_number: Optional[str] = None
    gender: Optional[Gender] = None  # Custom Enum for gender options

    @model_validator(mode="before")
    def handle_empty_strings(cls, values: dict):
        """
        Convert empty strings to None for optional fields.
        """
        for field in ["nationality", "phone_number", "linkedin", "twitter", "bio"]:
            if values.get(field) == "":
                values[field] = None
        return values

    @field_validator("phone_number")
    def clean_and_prefix_phone_number(cls, value: Optional[str], info):
        """
        Standardizes the phone number by ensuring it has the correct country code
        based on the user's nationality. The phone number itself is cleaned and retained.
        """
        if not value:  # Allow None or empty string
            return None  # ✅ Instead of raising ValueError

        nationality = info.data.get("nationality")
        if not nationality:
            raise ValueError(
                "Phone number provided without nationality. Please provide both."
            )

        # Get the country code for the provided nationality
        country_code = country_code_mapping.get(nationality)
        if not country_code:
            raise ValueError(f"No country code found for nationality '{nationality}'.")

        # Remove any existing country code or non-numeric characters
        cleaned_value = re.sub(r"[^\d]", "", value)

        # Prefix with the correct country code
        return f"{country_code}{cleaned_value}"

    @field_validator("nationality")
    def validate_nationality_with_phone(cls, value: Optional[str], info):
        """
        Ensure nationality is provided if a phone number is specified.
        """
        phone_number = info.data.get("phone_number")
        if phone_number and not value:
            raise ValueError("Nationality is required when a phone number is provided.")
        return value


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
    username: str
    bio: Optional[str] = None
    profile_picture: Optional[str] = None
    nationality: Optional[str] = None
    linkedin: Optional[str] = None
    twitter: Optional[str] = None
    phone_number: Optional[str] = None
    gender: Optional[Gender] = None
    is_active: bool
    is_verified: bool
    is_admin: bool
    is_super_admin: bool
    is_expert: bool = False
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=obj.id,
            email=obj.email,
            first_name=obj.first_name,
            last_name=obj.last_name,
            username=obj.username,
            bio=getattr(obj, "bio", None),  # ✅ Safe access
            profile_picture=getattr(obj, "profile_picture", None),
            nationality=getattr(obj, "nationality", None),
            linkedin=getattr(obj, "linkedin", None),
            twitter=getattr(obj, "twitter", None),
            phone_number=getattr(obj, "phone_number", None),
            gender=getattr(obj, "gender", None),
            is_active=obj.is_active,
            is_verified=obj.is_verified,
            is_admin=obj.is_admin,
            is_super_admin=obj.is_super_admin,
            is_expert=obj.is_expert,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )

    class Config:
        from_attributes = True


class PasswordResetConfirmation(BaseModel):
    email: Optional[EmailStr] = None
    otp: str
    new_password: str
    confirm_new_password: str

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

    @field_validator("confirm_new_password")
    def passwords_match(cls, v, values):
        new_password = values.data.get("new_password")
        if new_password and not secrets.compare_digest(v, new_password):
            raise ValueError("Passwords do not match")
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


class AIMessageResponseModel(BaseModel):
    id: int
    user_id: int
    profile_id: Optional[int] = None
    content: str
    usage_metadata: Optional[Dict[str, Any]] = {}
    response_metadata: Optional[Dict[str, Any]] = {}
    additional_kwargs: Optional[Dict[str, Any]] = {}
    created_at: datetime

    # Optional: derived UI-friendly fields
    tags: Optional[list[str]] = []
    persona: Optional[str] = None

    class Config:
        from_attributes = True  # Enables compatibility with SQLAlchemy models


class ChatMessageSchema(BaseModel):
    id: int
    roomId: int
    message: str = Field(..., min_length=1)
    resourceUrls: List[str] = []
    tags: List[str] = []

    @field_validator("message")
    def sanitize_message(cls, v):
        return re.sub(r"\[/?INST\]|<\|im_start\|>|<\|im_end\|>", "", v).strip()
