from __future__ import annotations

import importlib
import json
import sys
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from models.outputs import MarkdownWriterOutput
from repos.db_service import ResearchDBService


MARKDOWN_OUTPUT_PAYLOAD = {
    "id": "6a4d415bd906239299fd3278",
    "research_synopsis": (
        "This thesis explores the diverse applications of AI in medical science, "
        "emphasizing the importance of human-in-the-loop and explainable AI "
        "frameworks for responsible clinical integration. It proposes a structured "
        "pathway to address current challenges, aiming to improve trust, efficacy, "
        "and adoption of AI technologies in healthcare."
    ),
    "sources": [
        (
            "Kun–Hsing Yu et al., Artificial intelligence in healthcare, "
            "Nature Biomedical Engineering, 2018"
        ),
        (
            "Basubrin O., Current Status and Future of Artificial Intelligence "
            "in Medicine, Cureus, 2025"
        ),
        (
            "Human in the loop artificial intelligence in healthcare, "
            "Int J Med Inform, 2026"
        ),
        (
            "Daniel Truhn et al., Artificial intelligence agents in cancer "
            "research and oncology, Nature Reviews Cancer, 2026"
        ),
        (
            "Rajpurkar P. et al., AI in health and medicine, "
            "Nature Medicine, 2022"
        ),
        (
            "Explainable Artificial Intelligence for Medical Applications, "
            "Sun et al., arXiv, 2024"
        ),
        (
            "A Review on Explainable Artificial Intelligence for Healthcare, "
            "Bharati et al., arXiv, 2023"
        ),
        (
            "Systematic review: human–LLM collaboration, "
            "npj Digital Medicine, 2026"
        ),
        (
            "Reddit-based systematic review ICU AI deployment limitations "
            "study, 2024"
        ),
        (
            "JAMA study on FDA AI/ML device reporting inadequacies "
            "(reddit summary)"
        ),
    ],
    "research_area": "Applications of Artificial Intelligence in Healthcare",
    "research_directory": (
        "/Users/gskalra/mydocs/AI/agentic-researchops-platform/"
        "research/Uses_of_AI_in_Medical_Science"
    ),
    "markdown_files": [
        (
            "/Users/gskalra/mydocs/AI/agentic-researchops-platform/"
            "research/Uses_of_AI_in_Medical_Science/abstract.md"
        ),
        *[
            (
                "/Users/gskalra/mydocs/AI/agentic-researchops-platform/"
                f"research/Uses_of_AI_in_Medical_Science/chapter_{index:02d}.md"
            )
            for index in range(1, 7)
        ],
        (
            "/Users/gskalra/mydocs/AI/agentic-researchops-platform/"
            "research/Uses_of_AI_in_Medical_Science/conclusion.md"
        ),
        (
            "/Users/gskalra/mydocs/AI/agentic-researchops-platform/"
            "research/Uses_of_AI_in_Medical_Science/references.md"
        ),
    ],
    "pdf_path": (
        "/Users/gskalra/mydocs/AI/agentic-researchops-platform/"
        "research/pdf/6a4d415bd906239299fd3278.pdf"
    ),
    "status": "document_generation_completed",
    "error": None,
}


def import_begin_research_module():
    """Import the workflow module without opening real database clients."""
    sys.modules.pop("guardrails.begin_research", None)
    with patch("repos.db_service.ResearchDBService"):
        return importlib.import_module("guardrails.begin_research")


class MongoAgentTests(unittest.IsolatedAsyncioTestCase):
    def test_start_research_requires_under_analysis_status(self) -> None:
        service = ResearchDBService.__new__(ResearchDBService)
        service.collection = MagicMock()
        service.collection.update_one.return_value = SimpleNamespace(
            matched_count=1
        )
        service.findById = MagicMock(
            return_value={
                "id": MARKDOWN_OUTPUT_PAYLOAD["id"],
                "status": "start_research",
            }
        )

        result = service.update_doc_status(
            MARKDOWN_OUTPUT_PAYLOAD["id"],
            "start_research",
        )

        update_filter, update_operation = (
            service.collection.update_one.call_args.args
        )
        self.assertEqual(update_filter["status"], "under_analysis")
        self.assertEqual(
            update_operation["$set"]["status"],
            "start_research",
        )
        self.assertEqual(result["status"], "start_research")

    def test_update_research_transitions_status_to_completed(self) -> None:
        service = ResearchDBService.__new__(ResearchDBService)
        service.collection = MagicMock()
        service.collection.update_one.return_value = SimpleNamespace(
            modified_count=1
        )
        service.findById = MagicMock(
            return_value={
                "id": MARKDOWN_OUTPUT_PAYLOAD["id"],
                "status": "research_completed",
            }
        )

        result = service.update_research(
            {
                "_id": MARKDOWN_OUTPUT_PAYLOAD["id"],
                "research_synopsis": MARKDOWN_OUTPUT_PAYLOAD[
                    "research_synopsis"
                ],
                "research_area": MARKDOWN_OUTPUT_PAYLOAD["research_area"],
                "sources": MARKDOWN_OUTPUT_PAYLOAD["sources"],
            }
        )

        update_filter, update_operation = (
            service.collection.update_one.call_args.args
        )
        self.assertEqual(update_filter["status"], "research_in_progress")
        self.assertEqual(
            update_operation["$set"]["status"],
            "research_completed",
        )
        self.assertEqual(result["status"], "research_completed")

    def test_failed_active_research_is_reset_for_retry(self) -> None:
        service = ResearchDBService.__new__(ResearchDBService)
        service.collection = MagicMock()
        service.collection.update_one.return_value = SimpleNamespace(
            matched_count=1
        )
        service.findById = MagicMock(
            return_value={
                "id": MARKDOWN_OUTPUT_PAYLOAD["id"],
                "status": "under_analysis",
            }
        )

        result = service.reset_research_for_retry(
            MARKDOWN_OUTPUT_PAYLOAD["id"]
        )

        update_filter, update_operation = (
            service.collection.update_one.call_args.args
        )
        self.assertEqual(
            update_filter["status"]["$in"],
            ["start_research", "research_in_progress"],
        )
        self.assertEqual(
            update_operation["$set"]["status"],
            "under_analysis",
        )
        self.assertEqual(result["status"], "under_analysis")

    async def test_use_mongo_agent_updates_generated_research_details(self) -> None:
        module = import_begin_research_module()
        markdown_output = MarkdownWriterOutput.model_validate(
            MARKDOWN_OUTPUT_PAYLOAD
        )
        mongo_payload = {
            "action": "UPDATE_RESEARCH_DETAILS",
            "_id": markdown_output.id,
            "research_synopsis": markdown_output.research_synopsis,
            "research_area": markdown_output.research_area,
            "sources": markdown_output.sources,
        }
        expected_result = SimpleNamespace(
            final_output={
                "success": True,
                "id": markdown_output.id,
            }
        )

        run_mock = AsyncMock(return_value=expected_result)
        with (
            patch.object(module.Runner, "run", run_mock),
            patch.object(module, "trace", return_value=nullcontext()),
        ):
            actual_result = await module.use_mongo_agent(mongo_payload)

        self.assertIs(actual_result, expected_result)
        run_mock.assert_awaited_once()

        called_agent, called_chat = run_mock.await_args.args
        self.assertIs(called_agent, module.mongo_agent)
        self.assertEqual(len(called_chat), 1)
        self.assertEqual(called_chat[0]["role"], "user")

        decoded_payload = json.loads(called_chat[0]["content"])
        self.assertEqual(decoded_payload, mongo_payload)
        self.assertEqual(decoded_payload["action"], "UPDATE_RESEARCH_DETAILS")
        self.assertEqual(decoded_payload["_id"], MARKDOWN_OUTPUT_PAYLOAD["id"])
        self.assertEqual(
            decoded_payload["research_synopsis"],
            MARKDOWN_OUTPUT_PAYLOAD["research_synopsis"],
        )
        self.assertEqual(
            decoded_payload["research_area"],
            MARKDOWN_OUTPUT_PAYLOAD["research_area"],
        )
        self.assertEqual(
            decoded_payload["sources"],
            MARKDOWN_OUTPUT_PAYLOAD["sources"],
        )
        self.assertNotIn("markdown_files", decoded_payload)
        self.assertNotIn("pdf_path", decoded_payload)


if __name__ == "__main__":
    unittest.main()
