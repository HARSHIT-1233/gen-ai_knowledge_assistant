from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=200)


class ConversationMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    use_knowledge: bool = Field(
        default=False,
        description="When true the assistant retrieves relevant document chunks before answering.",
    )


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    created_at: datetime


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class ConversationDetail(ConversationSummary):
    messages: list[ConversationMessage]


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]


class ConversationReply(BaseModel):
    conversation_id: str
    answer: str
    model: str
    messages: list[ConversationMessage]
    sources: list[dict] = Field(
        default_factory=list,
        description="Knowledge sources used when use_knowledge=true.",
    )
