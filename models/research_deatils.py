from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, SkipValidation
from enum import Enum


class Status(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNDER_ANALYSIS = "under_analysis"
    ANALYZED = "analyzed"
    PUBLISHED = "published"


class ResearchDetails(BaseModel):
    ## this would pe popluated after login part is added, for now it is lept optional
    userId: Optional[SkipValidation[str]] | None = Field(
        default=None, description="The user ID associated with the research project."
    )
    name: str = Field(..., description="The name of the research project.")
    topic: str = Field(..., description="The research topic for the project.")
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


class ResearchStatusResponse(BaseModel):
    id: str = Field(..., description="The MongoDB id of the research project.")
    name: str = Field(..., description="The name of the research project.")
    status: Status = Field(
        ..., description="The current status of the research project."
    )
