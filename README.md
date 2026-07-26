# Agentic ResearchOps Platform

Agentic ResearchOps Platform is a local research-management application that
uses multiple AI agents to validate a research topic, prepare a thesis, create
Markdown source files, generate a PDF, and track the complete workflow in
MongoDB.

The application provides:

- A FastAPI backend for creating, searching, starting, and deleting research.
- A Gradio login and research-management interface.
- MongoDB storage for research records and workflow status.
- ChromaDB semantic search for finding similar research topics.
- OpenAI agents for topic validation, research, document writing, MongoDB
  operations, and PDF generation.
- A filesystem MCP server for controlled Markdown file access.
- ReportLab-based PDF generation.

## How the Project Works

### 1. Login

The Gradio application starts with a login screen. The current implementation
uses a local placeholder login profile and passes the user ID to the
controller. It is not a complete production authentication system.

### 2. Add a Research Topic

The user submits:

- User ID
- Project name
- Research topic
- Research area
- Initial synopsis
- Sources
- Funding status

The topic-validation agent checks:

1. Exact topic matches in MongoDB.
2. Semantically similar topics in ChromaDB.
3. External context through the DuckDuckGo API when required.

An approved topic is saved in MongoDB and indexed in ChromaDB with the
`under_analysis` status.

### 3. Search Research Records

Records can be searched by topic or user ID. The Gradio table displays every
matching record with:

- Topic
- Status
- User name
- Available action

The MongoDB document ID is retained internally but is not displayed.

### 4. Start Research

For a record with the `under_analysis` status, the UI displays a **Start
Research** button.

After it is clicked:

1. The clicked button is immediately disabled.
2. The UI displays **Research in progress…**.
3. Gradio sends the hidden MongoDB document ID to:

   ```text
   POST /research-details/begin-research?research_id=<document_id>
   ```

4. MongoDB atomically changes the status from `under_analysis` to
   `start_research`.
5. The Mongo agent claims the record and changes it from `start_research` to
   `research_in_progress`.

### 5. Conduct Research

The research agent gathers and organizes information for the approved topic.
Its structured output includes:

- Research synopsis
- Research area
- Background and problem statement
- Research gap
- Aim and objectives
- Verified sources
- Recommended thesis chapter structure
- Thesis content intended to represent approximately 30–50 pages

### 6. Create Markdown Files

The thesis-writing agent creates files under:

```text
research/<filesystem_safe_topic>/
```

The expected structure is:

```text
research/<filesystem_safe_topic>/
├── abstract.md
├── chapter_01.md
├── chapter_02.md
├── ...
├── conclusion.md
└── references.md
```

The filesystem MCP server is restricted to the project’s `research/`
directory. Every `.md` entry must be a non-empty regular file.

### 7. Generate the PDF

The PDF agent passes the verified Markdown files to the ReportLab PDF tool.
PDFs are written to:

```text
research/pdf/<document_id>.pdf
```

For example:

```text
research/pdf/6a4d415bd906239299fd3278.pdf
```

The workflow verifies that the PDF exists, is inside `research/pdf`, has a
`.pdf` extension, and is not empty.

### 8. Complete or Retry Research

After successful document generation, MongoDB changes the status from
`research_in_progress` to `research_completed`.

The UI then removes the Start Research button and displays a **Download PDF**
button.

If the workflow fails:

1. The API returns the original error.
2. The active record is reset to `under_analysis`.
3. The Start Research button is enabled again for retry.

For statuses other than `under_analysis` and `research_completed`, the action
column displays `—`.

## Workflow Statuses

```text
under_analysis
    → start_research
    → research_in_progress
    → research_completed
```

On a workflow error, an active record is returned to `under_analysis` so it
can be retried.

## Project Structure

```text
api/
  controller.py                 FastAPI application and routes

guardrails/
  begin_research.py             Multi-agent research and document workflow
  prompts.py                    Instructions for all agents
  validate_research_topic.py    Topic-validation agent and tools

models/
  outputs.py                    Structured agent input/output models
  research_deatils.py           Research models and workflow status enum

repos/
  db_service.py                 MongoDB and ChromaDB operations

service/
  research_service.py           Application business logic

ui/
  login_gradio.py               Main login and research-management UI
  research_details_gradio.py    UI helpers and search functions

util/
  pdf_writer.py                 Markdown-to-PDF ReportLab tool

tests/
  test_begin_research_controller.py
  test_login_gradio.py
  test_markdown_file_agent.py
  test_mongo_agent.py

research/
  <topic>/                      Generated Markdown files
  pdf/                          Generated <document_id>.pdf files
```

## Prerequisites

Install or provide:

1. Python 3.13 or newer.
2. [`uv`](https://docs.astral.sh/uv/).
3. MongoDB.
4. ChromaDB.
5. Node.js and `npx` for the filesystem MCP server.
6. An OpenAI API key.
7. Internet access for OpenAI, DuckDuckGo, and the first `npx` MCP package
   download.

Verify the main commands:

```bash
python3 --version
uv --version
node --version
npx --version
```

## Installation

### 1. Open the project directory

```bash
cd /Users/gskalra/mydocs/AI/agentic-researchops-platform
```

### 2. Install Python dependencies

```bash
uv sync
```

### 3. Configure environment variables

Create `.env` in the project root:

```env
OPENAI_API_KEY=your_openai_api_key

MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=research_db
MONGO_COLLECTION_NAME=research_details

CHROMA_HOST=localhost
CHROMA_PORT=8000
CHROMA_COLLECTION_NAME=research_db

RESEARCH_API_BASE_URL=http://127.0.0.1:8001
BEGIN_RESEARCH_TIMEOUT_SECONDS=3600
```

Do not commit `.env`. It is already excluded by `.gitignore`.

## Running the Project

The project requires MongoDB, ChromaDB, FastAPI, and Gradio.

### Step 1: Start MongoDB

Start your local MongoDB service. On macOS with Homebrew, this is commonly:

```bash
brew services start mongodb-community
```

If MongoDB is hosted elsewhere, set its connection string in `MONGO_URI`
instead.

### Step 2: Start ChromaDB

Open a terminal in the project root and run:

```bash
uv run chroma run --host 127.0.0.1 --port 8000
```

Keep this terminal open.

### Step 3: Start FastAPI and Gradio

Open another terminal in the project root and run:

```bash
uv run uvicorn api.controller:app --host 127.0.0.1 --port 8001 & api_pid=$!; trap 'kill $api_pid 2>/dev/null' EXIT INT TERM; uv run python -m ui.login_gradio
```

This command:

1. Starts FastAPI on port `8001`.
2. Saves the FastAPI process ID.
3. Starts Gradio on port `7860`.
4. Stops FastAPI automatically when the combined command exits.

### Step 4: Open the UI

Open:

```text
http://127.0.0.1:7860
```

### Step 5: Open the API documentation

Open:

```text
http://127.0.0.1:8001/docs
```

### Step 6: Stop the application

In the terminal running FastAPI and Gradio, press:

```text
Ctrl+C
```

The shell trap stops the FastAPI background process as Gradio exits.

## Running Services Separately

FastAPI:

```bash
uv run uvicorn api.controller:app --host 127.0.0.1 --port 8001
```

Gradio:

```bash
uv run python -m ui.login_gradio
```

ChromaDB:

```bash
uv run chroma run --host 127.0.0.1 --port 8000
```

## API Endpoints

### Health check

```text
GET /health
```

Example:

```bash
curl http://127.0.0.1:8001/health
```

### Create a research record

```text
POST /research-details/
```

Example:

```bash
curl -X POST http://127.0.0.1:8001/research-details/ \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "user-123",
    "name": "AI in Healthcare",
    "topic": "Applications of artificial intelligence in healthcare",
    "status": "pending",
    "is_granted": false,
    "research_area": "Medical Artificial Intelligence",
    "sources": [],
    "research_synopsis": "Study the responsible use of AI in healthcare."
  }'
```

### Search by user ID

```text
GET /research-details/<user_id>/status
```

Example:

```bash
curl http://127.0.0.1:8001/research-details/user-123/status
```

### Search by topic

```text
GET /research-details/by-name/<topic>/status
```

Example:

```bash
curl "http://127.0.0.1:8001/research-details/by-name/Applications%20of%20artificial%20intelligence%20in%20healthcare/status"
```

### Start research

```text
POST /research-details/begin-research?research_id=<document_id>
```

Example:

```bash
curl -X POST \
  "http://127.0.0.1:8001/research-details/begin-research?research_id=6a4d415bd906239299fd3278"
```

This request is synchronous and may take several minutes while research,
Markdown, and PDF agents execute.

### Delete research

```text
DELETE /research-details/<document_id>/status
```

## Run Tests

Run the focused test suite with the project virtual environment:

```bash
PYTHONPATH=. .venv/bin/python -m unittest \
  tests.test_begin_research_controller \
  tests.test_login_gradio \
  tests.test_markdown_file_agent \
  tests.test_mongo_agent
```

You may see non-fatal `ResourceWarning` messages from imported Gradio or
asyncio components. The test result should still end with `OK`.

## Generated Files

Generated research artifacts are stored under `research/`, which is excluded
from Git:

```text
research/
├── <filesystem_safe_topic>/
│   ├── abstract.md
│   ├── chapter_XX.md
│   ├── conclusion.md
│   └── references.md
└── pdf/
    └── <document_id>.pdf
```

## Troubleshooting

### ChromaDB connection failure

Confirm ChromaDB is running on the host and port configured in `.env`:

```bash
curl http://127.0.0.1:8000/api/v2/heartbeat
```

### MongoDB connection failure

Confirm MongoDB is running and `MONGO_URI` is correct.

### `npx` was not found

Install Node.js and ensure `node` and `npx` are available on `PATH`.

### `Server not initialized`

Filesystem MCP operations must execute inside the connected MCP server
context. Use the normal application workflow instead of directly running an
unconnected agent.

### PDF is not displayed

For completed research, the UI expects:

```text
research/pdf/<document_id>.pdf
```

Confirm that the ID exactly matches the hidden MongoDB document ID and that
the file is non-empty.

### Port already in use

Check ports `8000`, `8001`, and `7860`. Stop the older service instance before
starting another one.

## Development Notes

- The main UI is `ui.login_gradio`, not the older standalone helper module.
- FastAPI runs on `8001` because ChromaDB uses `8000`.
- The research endpoint runs synchronously and the UI timeout defaults to one
  hour.
- The filename `models/research_deatils.py` contains an existing spelling
  error. Imports must continue using that filename unless it is renamed
  consistently throughout the project.
- Generated research documents and `.env` are intentionally ignored by Git.
