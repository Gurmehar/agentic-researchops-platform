from __future__ import annotations

from pydantic import BaseModel, Field
from enum import Enum


class ResearchDetails(BaseModel):
    name: str = Field(..., description="The name of the research project.")
    status: Status = Field(
        ..., description="The current status of the research project."
    )
    is_granted: bool = Field(
        ...,
        description="Indicates whether the research project has been granted funding.",
    )
    research_area: str = Field(
        ..., description="The specific area of research for the project."
    )
    sources: list[str] = Field(
        ...,
        description="A list of sources or references related to the research project.",
    )
    research_synopsis: str = Field(
        ..., description="A brief summary or synopsis of the research project."
    )


class Status(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNDER_ANALYSIS = "under_analysis"
    ANALYZED = "analyzed"
    PUBLISHED = "published"
