import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import shutil
from agents import Agent, Runner, trace, function_tool, WebSearchTool
from dotenv import load_dotenv
from pydantic import BaseModel
from guardrails import prompts
from models.outputs import (
    FetchAndClaimOutput,
    BeginResearchOutput,
    MarkdownWriterOutput,
    PDFWriterOutput,
    PDFWriterInput,
)
from repos.db_service import ResearchDBService
from agents.mcp import MCPServerStdio
from util.pdf_writer import create_pdf

# from models.research_details import ResearchDetails, ResearchStatusResponse, Status

db_service = ResearchDBService()

load_dotenv(override=True)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESEARCH = PROJECT_ROOT / "research/"
PDF_LOC = RESEARCH / "pdf/"
MARKDOWN_AGENT_MAX_TURNS = 50
PDF_AGENT_MAX_TURNS = 30


def _node_command_environment() -> tuple[str, dict[str, str]]:
    """Return an npx executable and environment that can also resolve node."""
    homebrew_bin = Path("/opt/homebrew/bin")
    npx = shutil.which("npx")
    if npx is None and (homebrew_bin / "npx").is_file():
        npx = str(homebrew_bin / "npx")

    if npx is None:
        raise RuntimeError(
            "Node.js is required for the MCP servers, but npx was not found. "
            "Install Node.js or add its bin directory to PATH."
        )

    env = os.environ.copy()
    npx_bin = str(Path(npx).parent)
    env["PATH"] = os.pathsep.join(
        entry for entry in (npx_bin, env.get("PATH", "")) if entry
    )
    return npx, env


async def register_filesystem_mcp():
    """Register the MCP server with the MCP registry."""
    print(f"Registering filesystem MCP server with sandbox path: {RESEARCH}")
    npx, env = _node_command_environment()
    return MCPServerStdio(
        name="filesystem",
        params={
            "command": npx,
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                str(RESEARCH.resolve()),
            ],
            "env": env,
        },
        client_session_timeout_seconds=60,
    )


def _resolve_research_artifact(path_value: str) -> Path:
    """Resolve an agent-returned artifact path inside the research directory."""
    candidate = Path(path_value).expanduser()
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        if candidate.parts and candidate.parts[0] == RESEARCH.name:
            resolved = (PROJECT_ROOT / candidate).resolve()
        else:
            resolved = (RESEARCH / candidate).resolve()

    research_root = RESEARCH.resolve()
    if not resolved.is_relative_to(research_root):
        raise RuntimeError(f"Artifact is outside the research directory: {path_value}")

    if not resolved.exists():
        relative_path = resolved.relative_to(research_root)
        safe_parts = [
            re.sub(r"[^A-Za-z0-9._-]+", "_", part).strip("_")
            for part in relative_path.parts
        ]
        safe_candidate = research_root.joinpath(*safe_parts)
        if safe_candidate.exists():
            resolved = safe_candidate

    return resolved


def _filesystem_safe_topic_name(topic: str) -> str:
    """Convert a research topic into the canonical filesystem directory name."""
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", topic).strip("._-")
    if not safe_name:
        raise ValueError("The research topic does not produce a valid directory name.")
    return safe_name


def _prepare_markdown_agent_chat(chat: list[dict]) -> list[dict]:
    """Add deterministic filesystem paths to the Markdown agent input."""
    prepared_chat: list[dict] = []
    for message in chat:
        prepared_message = dict(message)
        if message.get("role") == "user":
            content = message.get("content")
            payload = json.loads(content) if isinstance(content, str) else dict(content)
            research_data = payload.get("research_data")
            if not isinstance(research_data, dict):
                raise ValueError("Markdown agent input requires research_data.")

            topic = research_data.get("authoritative_topic")
            if not isinstance(topic, str) or not topic.strip():
                raise ValueError("Markdown agent input requires authoritative_topic.")

            topic_name = _filesystem_safe_topic_name(topic)
            research_directory = (RESEARCH / topic_name).resolve()
            research_directory.mkdir(parents=True, exist_ok=True)

            research_id = str(payload.get("id") or "").strip()
            if not re.fullmatch(r"[A-Za-z0-9_-]+", research_id):
                raise ValueError("Markdown agent input requires a filesystem-safe id.")

            abstract_path = research_directory / "abstract.md"
            if not abstract_path.exists() or abstract_path.stat().st_size == 0:
                synopsis = research_data.get("research_synopsis")
                if not isinstance(synopsis, str) or not synopsis.strip():
                    raise ValueError(
                        "Markdown agent input requires research_synopsis "
                        "to create abstract.md."
                    )
                abstract_path.write_text(
                    f"# Abstract\n\n{synopsis.strip()}\n",
                    encoding="utf-8",
                )

            payload["topic_name"] = topic_name
            payload["research_directory"] = str(research_directory)
            payload["pdf_output_path"] = str((PDF_LOC / f"{research_id}.pdf").resolve())
            prepared_message["content"] = json.dumps(payload)

        prepared_chat.append(prepared_message)
    return prepared_chat


def _validate_markdown_writer_output(output: MarkdownWriterOutput) -> None:
    """Verify that a successful agent output is backed by real artifacts."""
    if output.status != "document_generation_completed":
        raise RuntimeError(output.error or "Document generation failed.")

    research_directory = _resolve_research_artifact(output.research_directory)
    if not research_directory.is_dir():
        raise RuntimeError(f"Research directory does not exist: {research_directory}")

    if not output.markdown_files:
        raise RuntimeError("The Markdown agent returned no Markdown files.")

    missing_or_empty_markdown: list[str] = []
    for path_value in output.markdown_files:
        markdown_path = _resolve_research_artifact(path_value)
        if (
            not markdown_path.is_relative_to(research_directory)
            or not markdown_path.is_file()
            or markdown_path.suffix.lower() != ".md"
            or markdown_path.stat().st_size == 0
        ):
            missing_or_empty_markdown.append(str(markdown_path))

    if missing_or_empty_markdown:
        raise RuntimeError(
            "Missing, empty, or invalid Markdown files: "
            + ", ".join(missing_or_empty_markdown)
        )

    if not output.pdf_path:
        raise RuntimeError("The Markdown agent returned no PDF path.")

    pdf_path = _resolve_research_artifact(output.pdf_path)
    pdf_directory = PDF_LOC.resolve()
    if (
        not pdf_path.is_relative_to(pdf_directory)
        or not pdf_path.is_file()
        or pdf_path.suffix.lower() != ".pdf"
        or pdf_path.stat().st_size == 0
    ):
        raise RuntimeError(f"PDF was not generated or is empty: {pdf_path}")


async def use_markdown_file_agent(chat: list[dict]) -> MarkdownWriterOutput:
    print(f"Using Markdown File Agent")
    prepared_chat = _prepare_markdown_agent_chat(chat)

    filesystem_server = await register_filesystem_mcp()

    async with filesystem_server:
        pdf_agent = Agent(
            name="PDF Writer Agent",
            instructions=prompts.PDF_WRITER_AGENT_INSTRUCTIONS,
            output_type=PDFWriterOutput,
            model="gpt-4.1-mini",
            tools=[create_pdf],
            mcp_servers=[filesystem_server],
        )

        pdf_agent_tool = pdf_agent.as_tool(
            tool_name="generate_thesis_pdf",
            tool_description=(
                "Generate the final thesis PDF after all Markdown "
                "files have been successfully created and verified."
            ),
            parameters=PDFWriterInput,
            include_input_schema=True,
            max_turns=PDF_AGENT_MAX_TURNS,
        )
        md_file_agent = Agent(
            name="Thesis Writer Agent",
            instructions=prompts.MARKDOWN_FILE_AGENT_INSTRUCTIONS,
            model="gpt-4.1-nano",
            mcp_servers=[filesystem_server],
            output_type=MarkdownWriterOutput,
            tools=[
                pdf_agent_tool,
            ],
        )
        with trace("Markdown File Agent"):
            result = await Runner.run(
                md_file_agent,
                prepared_chat,
                max_turns=MARKDOWN_AGENT_MAX_TURNS,
            )
            output = result.final_output
            _validate_markdown_writer_output(output)
            return output


@function_tool
def _fetch_matching_topics(topic_name: str) -> list[dict]:
    """Fetch MongoDB Docs with exact matching names."""
    return db_service.fetch_matching_topics(topic_name)


@function_tool
def _fetch_matching_id(id: str) -> list[dict]:
    """Fetch MongoDB Docs with exact matching names."""
    return db_service.findById(id)


@function_tool
def _update_research_status(id: str, status: str) -> list[dict]:
    """Fetch MongoDB Docs with exact matching names."""
    return db_service.update_doc_status(id, str(status))


@function_tool
def _update_research(
    id: str,
    research_synopsis: str,
    research_area: str,
    sources: list[str],
) -> dict | None:
    """Update details for a research-in-progress MongoDB document."""
    doc = {
        "_id": id,
        "research_synopsis": research_synopsis,
        "research_area": research_area,
        "sources": list(dict.fromkeys(sources)),
    }
    return db_service.update_research(doc)


mongo_agent = Agent(
    name="Mongo Agent",
    instructions=prompts.MONGODB_AGENT_INSTRUCTIONS,
    model="gpt-4.1-nano",
    tools=[
        _update_research_status,
        _update_research,
        _fetch_matching_id,
        _fetch_matching_topics,
    ],
    output_type=FetchAndClaimOutput,
)

research_agent = Agent(
    name="Research Agent",
    instructions=prompts.RESEARCH_AGENT_INSTRUCTIONS,
    model="gpt-4.1",
    tools=[
        WebSearchTool(),
    ],
    output_type=BeginResearchOutput,
)


async def use_research_agent(payload: dict) -> BeginResearchOutput:
    print(f"Using Research Agent with input: {payload}")
    chat = [
        {
            "role": "user",
            "content": json.dumps(payload),
        }
    ]
    with trace("Research Agent"):
        result = await Runner.run(research_agent, chat)
        return result.final_output


async def use_mongo_agent(payload: dict) -> dict:
    print(f"Using Mongo Agent with input: {payload}")
    chat = [
        {
            "role": "user",
            "content": json.dumps(payload),
        }
    ]
    with trace("Mongo Agent"):
        result = await Runner.run(mongo_agent, chat)
        return result


def main(id: str, topic: str):
    print("Starting research agent...")
    result = asyncio.run(
        use_mongo_agent(
            {
                "action": "FETCH_AND_CLAIM",
                "_id": id,
                "topic": topic,
            }
        )
    )
    print("Topic fetched. Starting research agent...")
    if isinstance(result.final_output, BaseModel):
        var = FetchAndClaimOutput.model_validate_json(
            result.final_output.model_dump_json()
        )
        result = asyncio.run(
            use_research_agent(
                {
                    "_id": var.id,
                    "topic": var.topic,
                    "status": var.status,
                    "research_area": var.research_area,
                }
            )
        )
        print("Research Done, Generating Markdown and PDF...")
        markdown_payload = {
            "id": var.id,
            "research_data": result.model_dump(mode="json"),
        }

        chat = [
            {
                "role": "user",
                "content": json.dumps(markdown_payload),
            }
        ]
        result = asyncio.run(use_markdown_file_agent(chat))

        var = MarkdownWriterOutput.model_validate(result)
        print(
            "Markdown and PDF generated successfully. Updating research details in MongoDB..."
        )
        result = asyncio.run(
            use_mongo_agent(
                {
                    "action": "UPDATE_RESEARCH_DETAILS",
                    "_id": var.id,
                    "research_synopsis": var.research_synopsis,
                    "research_area": var.research_area,
                    "sources": var.sources,
                }
            )
        )
        return result.final_output
    else:
        return json.dumps(result.final_output)


# if __name__ == "__main__":
#     main("6a4e64215174e22c451091ac", "Altering DNA of rice for better production")
