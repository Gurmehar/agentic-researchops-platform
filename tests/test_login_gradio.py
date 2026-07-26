from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


def import_login_module():
    sys.modules.pop("ui.login_gradio", None)
    with patch("repos.db_service.ResearchDBService"):
        return importlib.import_module("ui.login_gradio")


class LoginGradioResearchActionTests(unittest.TestCase):
    def test_mark_research_running_disables_selected_row_state(self) -> None:
        module = import_login_module()
        records = [
            {
                "id": "document-id",
                "topic": "Test topic",
                "status": "under_analysis",
            }
        ]

        button_update, selected_id, message = module._mark_research_running(
            "document-id",
        )

        self.assertEqual(selected_id, "document-id")
        self.assertIn("Please wait", message)
        self.assertFalse(button_update["interactive"])
        self.assertEqual(
            button_update["value"],
            "Research in progress…",
        )

    def test_start_research_calls_api_and_exposes_completed_pdf(self) -> None:
        module = import_login_module()
        records = [
            {
                "id": "document-id",
                "topic": "Uses of AI in Medical Science",
                "status": "under_analysis",
                "name": "Research User",
            }
        ]
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "id": "document-id",
            "name": "Research User",
            "status": "research_completed",
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            pdf_directory = Path(temporary_directory)
            pdf_path = (
                pdf_directory
                / "document-id.pdf"
            )
            pdf_path.write_bytes(b"%PDF-1.4\nvalidated")

            with (
                patch.object(module, "PDF_DIRECTORY", pdf_directory),
                patch.object(module.requests, "post", return_value=response) as post,
            ):
                message, updated_records = module._start_research(
                    "document-id",
                    records,
                )

        post.assert_called_once_with(
            module.BEGIN_RESEARCH_URL,
            params={"research_id": "document-id"},
            timeout=module.BEGIN_RESEARCH_TIMEOUT_SECONDS,
        )
        self.assertIn("ready to download", message)
        self.assertEqual(
            updated_records[0]["status"],
            "research_completed",
        )
        self.assertEqual(updated_records[0]["pdf_path"], str(pdf_path))

    def test_start_research_does_not_show_download_when_pdf_is_missing(self) -> None:
        module = import_login_module()
        records = [
            {
                "id": "document-id",
                "topic": "Missing PDF",
                "status": "under_analysis",
                "name": "Research User",
            }
        ]
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "id": "document-id",
            "name": "Research User",
            "status": "research_completed",
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            with (
                patch.object(module, "PDF_DIRECTORY", Path(temporary_directory)),
                patch.object(module.requests, "post", return_value=response),
            ):
                message, updated_records = module._start_research(
                    "document-id",
                    records,
                )

        self.assertIn("PDF file was not found", message)
        self.assertNotIn("pdf_path", updated_records[0])
        self.assertFalse(updated_records[0]["_research_running"])
        self.assertEqual(updated_records[0]["status"], "under_analysis")


if __name__ == "__main__":
    unittest.main()
