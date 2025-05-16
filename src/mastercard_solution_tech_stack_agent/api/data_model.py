from typing import Optional, Union

from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

from pydantic import BaseModel

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
