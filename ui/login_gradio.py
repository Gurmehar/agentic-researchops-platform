from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from uuid import uuid4

import gradio as gr
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.controller import receive_login_payload
from models.research_deatils import Status
from ui.research_details_gradio import (
    _research_items_from_response,
    search_research,
    submit_research_details,
)

LOGIN_SERVER_PORT = 7860
PDF_DIRECTORY = PROJECT_ROOT / "research" / "pdf"
RESEARCH_API_BASE_URL = os.getenv(
    "RESEARCH_API_BASE_URL",
    "http://127.0.0.1:8001",
).rstrip("/")
BEGIN_RESEARCH_URL = f"{RESEARCH_API_BASE_URL}/research-details/begin-research"
BEGIN_RESEARCH_TIMEOUT_SECONDS = int(
    os.getenv("BEGIN_RESEARCH_TIMEOUT_SECONDS", "3600")
)

LOGIN_PORTALS = {
    "Google": {
        "login_url": "https://accounts.google.com/signin",
        "instructions": "\n".join(
            [
                "1. Go to the app or website login page.",
                "2. Click Continue with Google.",
                "3. Select your Google account from the popup window.",
                "4. Click Confirm or Allow to grant access.",
                "5. No separate password is required.",
            ]
        ),
    },
    "LinkedIn": {
        "login_url": "https://www.linkedin.com/login",
        "instructions": "\n".join(
            [
                "1. Go to the platform's login page.",
                "2. Click Sign in with LinkedIn or Continue with LinkedIn.",
                "3. Enter your LinkedIn credentials if prompted.",
                "4. Click Allow Access to link your profile.",
            ]
        ),
    },
    "Twitter": {
        "login_url": "https://x.com/i/flow/login",
        "instructions": "\n".join(
            [
                "1. Go to the platform login page.",
                "2. Click Sign in with Twitter or Continue with Twitter.",
                "3. Enter your Twitter credentials if prompted.",
                "4. Authorize the app to link your profile.",
            ]
        ),
    },
}

LOGIN_PROVIDERS = list(LOGIN_PORTALS.keys())
DEFAULT_LOGIN_PROFILE = {
    "id": "611e1114-ca12-46d3-963c-cabe9ced24b3",
    "email": "",
    "name": "",
}

LOGIN_PAGE_CSS = """
#login-shell {
  max-width: 980px;
  margin: 0 auto;
  padding: 22px 34px 28px;
  font-family: Arial, sans-serif;
}

#platform-description {
  color: #111827;
  font-family: Arial, sans-serif;
  font-size: 20px;
  line-height: 1.45;
  margin: 0 0 28px;
}

#login-banner {
  width: 100%;
  border-radius: 9px;
  background: #6b9be3;
  color: #101828;
  font-size: 31px;
  line-height: 70px;
  text-align: center;
  font-weight: 400;
  margin-top: 12px;
}

.social-login-button {
  margin-bottom: 22px;
}

.social-login-button button {
  border: 2px solid #8bef18 !important;
  border-radius: 8px !important;
  box-shadow: none !important;
  color: #111827 !important;
  font-size: 34px !important;
  font-weight: 400 !important;
  height: 72px !important;
  justify-content: center !important;
  background: #ffffff !important;
}

.social-login-button button:hover {
  background: #fbfff5 !important;
  border-color: #7ddd12 !important;
}

.research-table-header {
  border-bottom: 2px solid #d1d5db;
  padding: 8px 12px 2px;
}

.research-table-row {
  align-items: center;
  border-bottom: 1px solid #e5e7eb;
  min-height: 64px;
  padding: 8px 12px;
}

.research-table-row > div,
.research-table-header > div {
  flex: 1 1 0;
  min-width: 0;
}

.google-login button::before {
  content: "G";
  color: #4285f4;
  font-size: 33px;
  font-weight: 700;
  margin-right: 18px;
}

.linkedin-login button::before {
  content: "in";
  background: #0a66c2;
  border-radius: 2px;
  color: #ffffff;
  font-size: 25px;
  font-weight: 700;
  line-height: 30px;
  margin-right: 18px;
  width: 30px;
  height: 30px;
  text-align: center;
}

.twitter-login button::before {
  content: "X";
  color: #111827;
  font-size: 30px;
  font-weight: 800;
  margin-right: 18px;
}

.response-panel {
  margin-top: 18px;
}
"""


def _parse_profile_json(raw_profile_json: str) -> dict[str, Any]:
    raw_value = raw_profile_json.strip()
    if not raw_value:
        return {}

    parsed_value = json.loads(raw_value)
    if not isinstance(parsed_value, dict):
        raise ValueError("Profile JSON must be an object.")

    return parsed_value


def _build_login_response(provider: str, profile: dict[str, Any]) -> dict[str, Any]:
    normalized_provider = provider.lower()
    user_id = profile.get("id") or profile.get("sub") or str(uuid4())

    return {
        "id": user_id,
        "provider": provider,
        "status": "success",
        "user": {
            "id": user_id,
            "email": profile.get("email", ""),
            "name": profile.get("name", ""),
            "profile_url": profile.get("profile_url", ""),
        },
        "auth": {
            "type": "oauth",
            "access_token": f"{normalized_provider}_access_token_pending_api",
            "refresh_token": f"{normalized_provider}_refresh_token_pending_api",
            "expires_in": 3600,
        },
        "received_at": datetime.now(UTC).isoformat(),
    }


def submit_login(
    provider: str, profile_json: str
) -> tuple[str, Any, Any, str]:
    try:
        profile = _parse_profile_json(profile_json)
        login_response = _build_login_response(provider, profile)
        controller_response = receive_login_payload(login_response)
        controller_status = controller_response.get("status", "")
        user_id = controller_response.get("user_id") or ""
        login_panel = gr.update(visible=controller_status != "HTTP.OK")
        research_panel = gr.update(visible=controller_status == "HTTP.OK")
        return controller_status, login_panel, research_panel, user_id
    except json.JSONDecodeError as exc:
        _error_response = {
            "message": "Invalid JSON.",
            "detail": exc.msg,
            "line": exc.lineno,
            "column": exc.colno,
        }
        return "", gr.update(visible=True), gr.update(visible=False), ""
    except ValueError as exc:
        _error_response = {
            "message": "Validation failed.",
            "detail": str(exc),
        }
        return "", gr.update(visible=True), gr.update(visible=False), ""
    except Exception as exc:
        _error_response = {
            "message": "Unexpected error.",
            "detail": str(exc),
        }
        return "", gr.update(visible=True), gr.update(visible=False), ""


def submit_google_login(
    profile_json: str,
) -> tuple[str, Any, Any, str]:
    return submit_login("Google", profile_json)


def submit_linkedin_login(
    profile_json: str,
) -> tuple[str, Any, Any, str]:
    return submit_login("LinkedIn", profile_json)


def submit_twitter_login(
    profile_json: str,
) -> tuple[str, Any, Any, str]:
    return submit_login("Twitter", profile_json)


def submit_default_google_login() -> tuple[str, Any, Any, str]:
    return submit_login("Google", json.dumps(DEFAULT_LOGIN_PROFILE))


def submit_default_linkedin_login() -> tuple[str, Any, Any, str]:
    return submit_login("LinkedIn", json.dumps(DEFAULT_LOGIN_PROFILE))


def submit_default_twitter_login() -> tuple[str, Any, Any, str]:
    return submit_login("Twitter", json.dumps(DEFAULT_LOGIN_PROFILE))


def _pdf_path_for_record(item: dict[str, Any]) -> str | None:
    if str(item.get("status", "")).lower() != Status.RESEARCH_COMPLETED.value:
        return None

    research_id = str(item.get("id") or item.get("_id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", research_id):
        return None

    pdf_path = PDF_DIRECTORY / f"{research_id}.pdf"
    return str(pdf_path) if pdf_path.is_file() and pdf_path.stat().st_size > 0 else None


def _search_table_records(
    search_type: str,
    search_value: str,
) -> tuple[str, list[dict[str, Any]]]:
    response = search_research(search_type, search_value)
    items = _research_items_from_response(response)

    if items:
        message = f"Found {len(items)} research record(s)."
    else:
        message = str(response.get("message", "No research found."))

    return message, items


def _start_research(
    research_id: str,
    records: list[dict[str, Any]] | None,
) -> tuple[str, list[dict[str, Any]]]:
    current_records = [dict(record) for record in records or []]
    selected_record = next(
        (
            record
            for record in current_records
            if str(record.get("id") or record.get("_id") or "") == research_id
        ),
        None,
    )

    def finish_with_error(message: str) -> tuple[str, list[dict[str, Any]]]:
        if selected_record is not None:
            selected_record["_research_running"] = False
            selected_record["status"] = Status.UNDER_ANALYSIS.value
            selected_record.pop("pdf_path", None)
        return message, current_records

    if not research_id:
        return finish_with_error(
            "Unable to start research: the record ID is unavailable.",
        )

    try:
        response = requests.post(
            BEGIN_RESEARCH_URL,
            params={"research_id": research_id},
            timeout=BEGIN_RESEARCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        response_data = response.json()

        if isinstance(response_data, dict) and response_data.get("error"):
            return finish_with_error(
                f"Research failed: {response_data['error']}",
            )

        api_status = (
            str(response_data.get("status", "")).lower()
            if isinstance(response_data, dict)
            else ""
        )
        if api_status != Status.RESEARCH_COMPLETED.value:
            return finish_with_error(
                "The research API returned without an error, but the record "
                f"status is `{api_status or 'unknown'}` instead of "
                f"`{Status.RESEARCH_COMPLETED.value}`."
            )

        if selected_record is None:
            return (
                "Research completed, but the selected row could not be refreshed.",
                current_records,
            )

        selected_record["status"] = Status.RESEARCH_COMPLETED.value
        selected_record["_research_running"] = False
        pdf_path = _pdf_path_for_record(selected_record)
        if not pdf_path:
            selected_record["status"] = str(
                response_data.get("status", selected_record["status"])
            )
            return finish_with_error(
                "Research completed without an API error, but the PDF file "
                "was not found under research/pdf.",
            )

        selected_record["pdf_path"] = pdf_path
        return (
            "Research completed successfully. The PDF is ready to download.",
            current_records,
        )
    except requests.HTTPError as exc:
        detail = ""
        if exc.response is not None:
            try:
                error_payload = exc.response.json()
                detail = str(
                    error_payload.get("detail")
                    or error_payload.get("error")
                    or ""
                )
            except (TypeError, ValueError):
                detail = ""
        return finish_with_error(
            f"Research failed: {detail or exc}"
        )
    except requests.RequestException as exc:
        return finish_with_error(
            f"Unable to start research through the API: {exc}"
        )
    except (TypeError, ValueError) as exc:
        return finish_with_error(
            f"Invalid response from the research API: {exc}"
        )


def _mark_research_running(
    research_id: str,
) -> tuple[Any, str, str]:
    return (
        gr.update(
            value="Research in progress…",
            interactive=False,
        ),
        research_id,
        "Research is running. Please wait for completion…",
    )


with gr.Blocks(title="Login") as demo:
    with gr.Column(elem_id="login-shell") as login_shell:
        gr.HTML(
            '<p id="platform-description">'
            "Agentic ResearchOps Platform is a small research-topic intake and "
            "validation app. It accepts research project details, validates the "
            "submitted topic with an AI agent, checks existing topics in MongoDB "
            "and ChromaDB, and stores approved research records for later status "
            "lookup.<br><br>"
            "The project exposes both a FastAPI backend and a Gradio UI."
            "</p>"
        )
        google_button = gr.Button(
            "Continue with Google",
            elem_classes=["social-login-button", "google-login"],
        )
        linkedin_button = gr.Button(
            "Continue with LinkedIn",
            elem_classes=["social-login-button", "linkedin-login"],
        )
        twitter_button = gr.Button(
            "Continue with Twitter",
            elem_classes=["social-login-button", "twitter-login"],
        )
        gr.HTML('<div id="login-banner">Log in</div>')

        with gr.Column(elem_classes=["response-panel"]):
            controller_status_output = gr.Textbox(visible=False)

    with gr.Column(elem_id="research-shell", visible=False) as research_shell:
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
                    placeholder=(
                        "Enter one source per line, or separate sources with commas."
                    ),
                    lines=4,
                )
                research_synopsis_input = gr.Textbox(
                    label="Research synopsis",
                    lines=6,
                )

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

                search_button = gr.Button("Search", variant="primary")
                search_status = gr.Markdown()
                search_records = gr.State([])
                selected_research_id = gr.State("")
                action_status = gr.Markdown()

                with gr.Row(elem_classes=["research-table-header"]):
                    gr.Markdown("**Topic**")
                    gr.Markdown("**Status**")
                    gr.Markdown("**User name**")
                    gr.Markdown("**Action / PDF**")

                @gr.render(inputs=search_records)
                def render_search_records(
                    records: list[dict[str, Any]] | None,
                ) -> None:
                    for record in records or []:
                        research_id = str(
                            record.get("id") or record.get("_id") or ""
                        )
                        topic = str(
                            record.get("topic") or record.get("name") or "—"
                        )
                        status = str(record.get("status") or "—")
                        user_name = str(
                            record.get("user_name") or record.get("name") or "—"
                        )
                        can_start = (
                            status.lower() == Status.UNDER_ANALYSIS.value
                            and bool(research_id)
                        )
                        is_running = bool(record.get("_research_running"))
                        pdf_path = _pdf_path_for_record(record)

                        with gr.Row(elem_classes=["research-table-row"]):
                            gr.Markdown(topic)
                            gr.Markdown(status)
                            gr.Markdown(user_name)
                            with gr.Column():
                                if is_running:
                                    gr.Button(
                                        "Research in progress…",
                                        interactive=False,
                                        size="sm",
                                    )
                                elif can_start:
                                    hidden_id = gr.State(research_id)
                                    start_button = gr.Button(
                                        "Start Research",
                                        variant="primary",
                                        size="sm",
                                    )
                                    start_event = start_button.click(
                                        fn=_mark_research_running,
                                        inputs=[hidden_id],
                                        outputs=[
                                            start_button,
                                            selected_research_id,
                                            action_status,
                                        ],
                                        queue=False,
                                    )
                                    start_event.then(
                                        fn=_start_research,
                                        inputs=[
                                            selected_research_id,
                                            search_records,
                                        ],
                                        outputs=[action_status, search_records],
                                        show_progress="full",
                                        concurrency_limit=1,
                                        concurrency_id=f"research-{research_id}",
                                    )
                                elif pdf_path:
                                    gr.DownloadButton(
                                        "Download PDF",
                                        value=pdf_path,
                                        size="sm",
                                    )
                                else:
                                    gr.Markdown("—")

                search_button.click(
                    fn=_search_table_records,
                    inputs=[search_type_input, search_value_input],
                    outputs=[search_status, search_records],
                )

        google_event = google_button.click(
            fn=submit_default_google_login,
            inputs=None,
            outputs=[
                controller_status_output,
                login_shell,
                research_shell,
                user_id_input,
            ],
        )
        linkedin_event = linkedin_button.click(
            fn=submit_default_linkedin_login,
            inputs=None,
            outputs=[
                controller_status_output,
                login_shell,
                research_shell,
                user_id_input,
            ],
        )
        twitter_event = twitter_button.click(
            fn=submit_default_twitter_login,
            inputs=None,
            outputs=[
                controller_status_output,
                login_shell,
                research_shell,
                user_id_input,
            ],
        )


if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        server_port=LOGIN_SERVER_PORT,
        css=LOGIN_PAGE_CSS,
    )
