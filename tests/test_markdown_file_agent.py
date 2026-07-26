from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from models.outputs import MarkdownWriterOutput, PDFWriterInput

MARKDOWN_PAYLOAD = {
    "id": "6a4d415bd906239299fd3278",
    "research_data": {
        "authoritative_topic": "Uses of AI in Medical Science",
        "identified_research_area": "Artificial Intelligence in Healthcare",
        "research_synopsis": (
            "This research examines how artificial intelligence supports medical "
            "diagnosis, treatment planning, and clinical decision-making while "
            "addressing reliability, bias, privacy, governance, and responsible "
            "adoption across modern healthcare systems."
        ),
        "background": "AI is increasingly used across clinical workflows.",
        "problem_statement": (
            "Healthcare AI requires evidence of safety, reliability, and fairness."
        ),
        "research_gap": (
            "Implementation evidence remains fragmented across clinical settings."
        ),
        "aim": "Evaluate responsible applications of AI in medical science.",
        "research_objectives": (
            "Assess applications, benefits, limitations, risks, and governance."
        ),
        "research_questions": (
            "How can healthcare systems adopt AI safely and effectively?"
        ),
        "hypotheses": None,
        "scope": "Clinical diagnosis, treatment, operations, and governance.",
        "significance": (
            "The research supports evidence-based healthcare AI adoption."
        ),
        "literature_findings": (
            "Published evidence reports both clinical promise and material risks."
        ),
        "proposed_methodology": (
            "A structured review and comparative synthesis of verified sources."
        ),
        "important_concepts": (
            "Clinical AI, explainability, bias, privacy, safety, and governance."
        ),
        "relevant_datasets_or_systems": (
            "Medical imaging, electronic health records, and decision-support systems."
        ),
        "findings_supported_by_sources": (
            "AI can support clinicians when appropriately validated and monitored."
        ),
        "limitations": (
            "Evidence quality and generalizability vary across clinical environments."
        ),
        "expected_contribution": (
            "A practical synthesis of responsible healthcare AI adoption."
        ),
        "recommended_thesis_chapter_structure": (
            "Introduction; literature review; methodology; findings; discussion; "
            "conclusion."
        ),
        "verified_sources": [
            "https://www.who.int/publications/i/item/9789240029200",
        ],
        "thesis": (
            "# Uses of AI in Medical Science\n\n"
            "This fixture contains representative thesis content for orchestration "
            "testing. The external agents are mocked, so no files are generated."
        ),
        "estimated_page_count": 30,
        "source_to_chapter_mapping": [
            {
                "source": "https://www.who.int/publications/i/item/9789240029200",
                "chapter": "Literature Review",
            }
        ],
    },
}


class FakeFilesystemServer:
    def __init__(self) -> None:
        self.connected = False

    async def __aenter__(self) -> FakeFilesystemServer:
        self.connected = True
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        self.connected = False


def import_begin_research_module():
    """Import the module without opening real MongoDB or ChromaDB clients."""
    sys.modules.pop("guardrails.begin_research", None)
    with patch("repos.db_service.ResearchDBService"):
        return importlib.import_module("guardrails.begin_research")


class MarkdownFileAgentTests(unittest.IsolatedAsyncioTestCase):
    def test_resolves_unsanitized_topic_name_to_existing_safe_directory(self) -> None:
        module = import_begin_research_module()

        with tempfile.TemporaryDirectory() as temporary_directory:
            research_root = module.Path(temporary_directory)
            safe_topic_directory = research_root / "Uses_of_AI_in_Medical_Science"
            safe_topic_directory.mkdir()

            with patch.object(module, "RESEARCH", research_root):
                resolved = module._resolve_research_artifact(
                    "Uses of AI in Medical Science"
                )

            self.assertEqual(resolved, safe_topic_directory.resolve())

    def test_resolves_project_relative_research_path_without_duplication(self) -> None:
        module = import_begin_research_module()

        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = module.Path(temporary_directory)
            research_root = project_root / "research"
            topic_directory = research_root / "topic"
            topic_directory.mkdir(parents=True)

            with (
                patch.object(module, "PROJECT_ROOT", project_root),
                patch.object(module, "RESEARCH", research_root),
            ):
                resolved = module._resolve_research_artifact(
                    "research/topic/chapter_01.md"
                )

            self.assertEqual(
                resolved,
                (topic_directory / "chapter_01.md").resolve(),
            )

    def test_rejects_success_when_artifacts_are_missing(self) -> None:
        module = import_begin_research_module()

        with tempfile.TemporaryDirectory() as temporary_directory:
            research_root = module.Path(temporary_directory)
            topic_directory = research_root / "missing_artifacts"
            topic_directory.mkdir()
            output = MarkdownWriterOutput(
                id=MARKDOWN_PAYLOAD["id"],
                research_synopsis=MARKDOWN_PAYLOAD["research_data"][
                    "research_synopsis"
                ],
                sources=MARKDOWN_PAYLOAD["research_data"]["verified_sources"],
                research_area=MARKDOWN_PAYLOAD["research_data"][
                    "identified_research_area"
                ],
                research_directory=str(topic_directory),
                markdown_files=[str(topic_directory / "chapter_01.md")],
                pdf_path=str(topic_directory / "thesis.pdf"),
                status="document_generation_completed",
                error=None,
            )

            with patch.object(module, "RESEARCH", research_root):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "Missing, empty, or invalid Markdown files",
                ):
                    module._validate_markdown_writer_output(output)

    async def test_use_markdown_file_agent_orchestration(self) -> None:
        module = import_begin_research_module()
        filesystem_server = FakeFilesystemServer()
        pdf_agent = MagicMock(name="pdf_agent")
        markdown_agent = MagicMock(name="markdown_agent")
        pdf_agent_tool = MagicMock(name="generate_thesis_pdf")
        pdf_agent.as_tool.return_value = pdf_agent_tool

        chat = [
            {
                "role": "user",
                "content": json.dumps(MARKDOWN_PAYLOAD),
            }
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            research_root = module.Path(temporary_directory)
            topic_directory = research_root / "Uses_of_AI_in_Medical_Science"
            topic_directory.mkdir()
            markdown_path = topic_directory / "chapter_01.md"
            markdown_path.write_text("# Chapter 1\n\nValidated content.", encoding="utf-8")
            pdf_directory = research_root / "pdf"
            pdf_directory.mkdir()
            pdf_path = (
                pdf_directory
                / f"{MARKDOWN_PAYLOAD['id']}.pdf"
            )
            pdf_path.write_bytes(b"%PDF-1.4\nvalidation")

            expected_output = MarkdownWriterOutput(
                id=MARKDOWN_PAYLOAD["id"],
                research_synopsis=MARKDOWN_PAYLOAD["research_data"][
                    "research_synopsis"
                ],
                sources=MARKDOWN_PAYLOAD["research_data"]["verified_sources"],
                research_area=MARKDOWN_PAYLOAD["research_data"][
                    "identified_research_area"
                ],
                research_directory=str(topic_directory),
                markdown_files=[str(markdown_path)],
                pdf_path=str(pdf_path),
                status="document_generation_completed",
                error=None,
            )

            async def run_agent(agent, received_chat, *, max_turns):
                self.assertEqual(max_turns, module.MARKDOWN_AGENT_MAX_TURNS)
                self.assertTrue(
                    filesystem_server.connected,
                    "Runner.run must execute while the filesystem MCP server is connected.",
                )
                self.assertIs(agent, markdown_agent)
                received_payload = json.loads(received_chat[0]["content"])
                self.assertEqual(
                    received_payload["topic_name"],
                    "Uses_of_AI_in_Medical_Science",
                )
                self.assertEqual(
                    received_payload["research_directory"],
                    str(topic_directory.resolve()),
                )
                self.assertEqual(
                    received_payload["pdf_output_path"],
                    str(pdf_path.resolve()),
                )
                return SimpleNamespace(final_output=expected_output)

            with (
                patch.object(module, "RESEARCH", research_root),
                patch.object(module, "PDF_LOC", pdf_directory),
                patch.object(
                    module,
                    "register_filesystem_mcp",
                    AsyncMock(return_value=filesystem_server),
                ),
                patch.object(
                    module,
                    "Agent",
                    side_effect=[pdf_agent, markdown_agent],
                ) as agent_constructor,
                patch.object(module.Runner, "run", AsyncMock(side_effect=run_agent)),
                patch.object(module, "trace", return_value=nullcontext()),
            ):
                actual_output = await module.use_markdown_file_agent(chat)

            self.assertEqual(actual_output, expected_output)
            seeded_abstract = topic_directory / "abstract.md"
            self.assertTrue(seeded_abstract.is_file())
            self.assertIn(
                MARKDOWN_PAYLOAD["research_data"]["research_synopsis"],
                seeded_abstract.read_text(encoding="utf-8"),
            )
            self.assertIsInstance(actual_output, MarkdownWriterOutput)
            self.assertFalse(hasattr(actual_output, "final_output"))
        self.assertFalse(filesystem_server.connected)
        self.assertEqual(agent_constructor.call_count, 2)

        pdf_agent.as_tool.assert_called_once_with(
            tool_name="generate_thesis_pdf",
            tool_description=(
                "Generate the final thesis PDF after all Markdown "
                "files have been successfully created and verified."
            ),
            parameters=PDFWriterInput,
            include_input_schema=True,
            max_turns=module.PDF_AGENT_MAX_TURNS,
        )

        pdf_input_schema = PDFWriterInput.model_json_schema()
        self.assertIn("pdf_output_path", pdf_input_schema["required"])

        pdf_agent_call = agent_constructor.call_args_list[0]
        self.assertEqual(pdf_agent_call.kwargs["mcp_servers"], [filesystem_server])

        markdown_agent_call = agent_constructor.call_args_list[1]
        self.assertEqual(
            markdown_agent_call.kwargs["mcp_servers"],
            [filesystem_server],
        )
        self.assertEqual(markdown_agent_call.kwargs["tools"], [pdf_agent_tool])

        decoded_payload = json.loads(chat[0]["content"])
        self.assertEqual(decoded_payload["id"], MARKDOWN_PAYLOAD["id"])
        self.assertIn("research_data", decoded_payload)
        self.assertEqual(
            decoded_payload["research_data"]["authoritative_topic"],
            "Uses of AI in Medical Science",
        )


if __name__ == "__main__":
    unittest.main()
