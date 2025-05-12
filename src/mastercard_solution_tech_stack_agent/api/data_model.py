from typing import Optional, Union

from pydantic import BaseModel, Field


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
