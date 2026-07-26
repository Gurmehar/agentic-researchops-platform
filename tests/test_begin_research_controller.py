from __future__ import annotations

import importlib
import sys
import unittest
from unittest.mock import patch

from fastapi import HTTPException


def import_controller_module():
    sys.modules.pop("api.controller", None)
    with patch("repos.db_service.ResearchDBService"):
        return importlib.import_module("api.controller")


class BeginResearchControllerTests(unittest.TestCase):
    def test_starts_workflow_after_status_transition(self) -> None:
        controller = import_controller_module()
        completed = {
            "id": "document-id",
            "name": "Test topic",
            "status": "research_completed",
        }

        with (
            patch.object(
                controller.research_service,
                "update_topic_for_research",
                return_value={
                    "id": "document-id",
                    "name": "Test topic",
                    "status": "start_research",
                },
            ) as update_status,
            patch.object(
                controller.research_service,
                "send_topic_for_research",
                return_value=completed,
            ) as start_workflow,
        ):
            result = controller.begin_research("document-id")

        update_status.assert_called_once_with("document-id")
        start_workflow.assert_called_once_with("document-id")
        self.assertEqual(result, completed)

    def test_does_not_start_workflow_when_transition_fails(self) -> None:
        controller = import_controller_module()
        with (
            patch.object(
                controller.research_service,
                "update_topic_for_research",
                return_value=None,
            ),
            patch.object(
                controller.research_service,
                "send_topic_for_research",
            ) as start_workflow,
        ):
            with self.assertRaises(HTTPException) as raised:
                controller.begin_research("document-id")

        self.assertEqual(raised.exception.status_code, 409)
        start_workflow.assert_not_called()

    def test_returns_workflow_failure_as_http_error(self) -> None:
        controller = import_controller_module()
        with (
            patch.object(
                controller.research_service,
                "update_topic_for_research",
                return_value={
                    "id": "document-id",
                    "name": "Test topic",
                    "status": "start_research",
                },
            ),
            patch.object(
                controller.research_service,
                "send_topic_for_research",
                return_value={
                    "message": "Failed to save research details.",
                    "error": "PDF was not generated or is empty.",
                },
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                controller.begin_research("document-id")

        self.assertEqual(raised.exception.status_code, 500)
        self.assertEqual(
            raised.exception.detail,
            "PDF was not generated or is empty.",
        )


if __name__ == "__main__":
    unittest.main()
