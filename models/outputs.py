from __future__ import annotations
from typing import Literal

from pydantic import BaseModel, Field


class FetchAndClaimOutput(BaseModel):
    id: str
    topic: str
    status: str
    research_area: str


class SourceChapterMapping(BaseModel):
    source: str
    chapter: str


class BeginResearchOutput(BaseModel):
    authoritative_topic: str
    identified_research_area: str
    research_synopsis: str
    background: str
    problem_statement: str
    research_gap: str
    aim: str
    research_objectives: str
    research_questions: str
    hypotheses: str | None = None
    scope: str
    significance: str
    literature_findings: str
    proposed_methodology: str
    important_concepts: str
    relevant_datasets_or_systems: str
    findings_supported_by_sources: str
    limitations: str
    expected_contribution: str
    recommended_thesis_chapter_structure: str
    verified_sources: list[str]
    thesis: str
    estimated_page_count: int = Field(ge=30, le=50)
    source_to_chapter_mapping: list[SourceChapterMapping]


class MarkdownWriterOutput(BaseModel):
    id: str
    research_synopsis: str
    sources: list[str]
    research_area: str
    research_directory: str
    markdown_files: list[str]
    pdf_path: str | None
    status: Literal[
        "document_generation_completed",
        "document_generation_failed",
    ]
    error: str | None = None


class PDFWriterInput(BaseModel):
    id: str
    topic_name: str
    research_directory: str
    pdf_output_path: str


class PDFWriterOutput(BaseModel):
    id: str
    topic_name: str
    pdf_path: str | None
    status: str
    error: str | None = None
