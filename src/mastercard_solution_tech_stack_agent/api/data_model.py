from enum import Enum
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field


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
