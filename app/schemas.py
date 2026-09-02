from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TopicRequest(BaseModel):
    """A seed idea supplied by a StoryForge user."""

    topic: str = Field(
        min_length=3,
        max_length=200,
        examples=["The 1999 Mars Climate Orbiter failure"],
    )


class TopicResponse(BaseModel):
    """A saved documentary project."""

    id: str
    topic: str
    status: str
    created_at: datetime


class SourceRequest(BaseModel):
    """A source that may support a documentary's research."""

    title: str = Field(min_length=3, max_length=200)
    url: str = Field(min_length=8, max_length=2_000)
    notes: str = Field(default="", max_length=2_000)


class SourceResponse(SourceRequest):
    """A saved research source."""

    id: str
    project_id: str
    created_at: datetime
    extracted_text: str | None = None
    extracted_at: datetime | None = None


OutputLanguage = Literal["English", "Urdu", "Hindi", "Spanish"]


class ResearchGenerationRequest(BaseModel):
    language: OutputLanguage = "English"


class ResearchBriefResponse(BaseModel):
    project_id: str
    content: str
    language: OutputLanguage
    model: str
    generated_at: datetime
