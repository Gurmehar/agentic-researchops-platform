from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from pathlib import Path
import sys
from typing import Any

import gradio as gr
from fastapi import HTTPException
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.controller import (
    create_research_details,
    get_research_status,
    get_research_status_by_name,
    health_check,
)
from models.research_deatils import ResearchDetails, Status


def _parse_sources(raw_sources: str) -> list[str]:
    normalized_sources = raw_sources.replace(",", "\n")
    return [
        source.strip() for source in normalized_sources.splitlines() if source.strip()
    ]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def _format_response(response: Any) -> dict[str, Any]:
    if response is None or response == {} or response == []:
        return {"message": "No research found."}
    return _json_safe(response)


def submit_research_details(
    user_id: str,
    name: str,
    topic: str,
    status_value: str,
    is_granted: bool,
    research_area: str,
    sources: str,
    research_synopsis: str,
) -> dict[str, Any]:
    try:
        payload = ResearchDetails(
            userId=user_id.strip() or None,
            name=name,
            topic=topic,
            status=Status(status_value),
            is_granted=is_granted,
            research_area=research_area,
            sources=_parse_sources(sources),
            research_synopsis=research_synopsis,
        )
        return _format_response(create_research_details(payload))
    except ValidationError as exc:
        return {
            "message": "Validation failed.",
            "errors": exc.errors(),
        }
    except HTTPException as exc:
        return {
            "message": "API request failed.",
            "status_code": exc.status_code,
            "detail": exc.detail,
        }
    except Exception as exc:
        return {
            "message": "Unexpected error.",
            "detail": str(exc),
        }


def search_research(search_type: str, search_value: str) -> dict[str, Any]:
    value = search_value.strip()
    if not value:
        return {"message": "Enter a value to search."}

    try:
        if search_type == "Topic":
            response = get_research_status_by_name(value)
        else:
            response = get_research_status(value)
        return _format_response(response)
    except HTTPException as exc:
        if exc.status_code == 404:
            return {"message": "No research found."}
        return {
            "message": "API request failed.",
            "status_code": exc.status_code,
            "detail": exc.detail,
        }
    except Exception as exc:
        return {
            "message": "Unexpected error.",
            "detail": str(exc),
        }


def check_api_health() -> dict[str, Any]:
    return _format_response(health_check())


with gr.Blocks(title="Research Details") as demo:
    gr.Markdown("# Research Details")

    with gr.Tabs():
        with gr.Tab("Add Research Topic"):
            with gr.Row():
                user_id_input = gr.Textbox(label="User ID")
                name_input = gr.Textbox(label="Research project name")

            topic_input = gr.Textbox(label="Research topic")

            with gr.Row():
                status_input = gr.Dropdown(
                    label="Status",
                    choices=[status.value for status in Status],
                    value=Status.PENDING.value,
                )
                is_granted_input = gr.Checkbox(label="Funding granted")

            research_area_input = gr.Textbox(label="Research area")
            sources_input = gr.Textbox(
                label="Sources",
                placeholder="Enter one source per line, or separate sources with commas.",
                lines=4,
            )
            research_synopsis_input = gr.Textbox(label="Research synopsis", lines=6)

            submit_button = gr.Button("Submit", variant="primary")
            create_output = gr.JSON(label="API response")

            submit_button.click(
                fn=submit_research_details,
                inputs=[
                    user_id_input,
                    name_input,
                    topic_input,
                    status_input,
                    is_granted_input,
                    research_area_input,
                    sources_input,
                    research_synopsis_input,
                ],
                outputs=create_output,
            )

        with gr.Tab("Search Research"):
            search_type_input = gr.Radio(
                label="Search by",
                choices=["Topic", "User ID"],
                value="Topic",
            )
            search_value_input = gr.Textbox(label="Search value")

            with gr.Row():
                search_button = gr.Button("Search", variant="primary")
                health_button = gr.Button("Health")

            search_output = gr.JSON(label="API response")

            search_button.click(
                fn=search_research,
                inputs=[search_type_input, search_value_input],
                outputs=search_output,
            )
            health_button.click(fn=check_api_health, outputs=search_output)


if __name__ == "__main__":
    demo.launch()
