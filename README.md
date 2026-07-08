# Agentic ResearchOps Platform

Agentic ResearchOps Platform is a small research-topic intake and validation app. It accepts research project details, validates the submitted topic with an AI agent, checks existing topics in MongoDB and ChromaDB, and stores approved research records for later status lookup.

The project exposes both a FastAPI backend and a Gradio UI.

## What It Does

- Accepts research details such as user id, project name, topic, sources, synopsis, research area, funding flag, and status.
- Uses an OpenAI Agents based validator to decide whether a topic should be approved, rejected, or revised.
- Checks MongoDB for exact topic matches.
- Checks ChromaDB for semantically similar topics.
- Uses DuckDuckGo search for external topic validation when needed.
- Saves accepted research details to MongoDB.
- Adds saved topics to ChromaDB for future semantic matching.
- Provides APIs and a Gradio UI to create research entries and search research status.

## Components Used

- `FastAPI`: REST API layer in `api/controller.py`.
- `Gradio`: local browser UI in `ui/research_details_gradio.py`.
- `Pydantic`: request and response models in `models/research_deatils.py`.
- `MongoDB`: persistent storage for research details.
- `ChromaDB`: vector store for semantic topic search.
- `OpenAI Agents SDK`: AI topic validation agent in `guardrails/validate_research_topic.py`.
- `DuckDuckGo Instant Answer API`: lightweight internet validation search.
- `uv`: Python dependency and command runner.

## Project Structure

```text
api/
  controller.py              FastAPI routes
guardrails/
  prompts.py                 AI validator prompt
  validate_research_topic.py OpenAI agent and tools
models/
  research_deatils.py        Pydantic models and status enum
repos/
  db_service.py              MongoDB and ChromaDB access layer
service/
  research_service.py        Business logic and validation flow
ui/
  research_details_gradio.py Gradio UI
```

## Prerequisites

- Python 3.13+
- `uv`
- MongoDB running locally or available through `MONGO_URI`
- ChromaDB server running locally or available through `CHROMA_HOST` and `CHROMA_PORT`
- OpenAI API key for the AI validator

## Environment Variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=research_db
MONGO_COLLECTION_NAME=research_details
CHROMA_HOST=localhost
CHROMA_PORT=8000
CHROMA_COLLECTION_NAME=research_db
```

## Install Dependencies

From the project root:

```bash
uv sync
```

If you are adding dependencies manually:

```bash
uv add fastapi uvicorn pymongo pydantic gradio chromadb langchain-chroma openai-agents requests dotenv
```

## Run Locally

Start MongoDB and ChromaDB first.

Example ChromaDB command:

```bash
chroma run --host localhost --port 8000
```

Run the FastAPI backend:

```bash
uv run uvicorn api.controller:app --reload
```

Open API docs:

```text
http://127.0.0.1:8000/docs
```

Run the Gradio UI:

```bash
uv run python ui/research_details_gradio.py
```

Gradio usually opens at:

```text
http://127.0.0.1:7860
```

## API Endpoints

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Create research details:

```bash
curl -X POST http://127.0.0.1:8000/research-details/ \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "user-123",
    "name": "Nutrition Study",
    "topic": "Effects of frozen food consumption on the nutrition and health of children below 15 years",
    "status": "pending",
    "is_granted": false,
    "research_area": "Nutrition",
    "sources": ["https://example.com/source"],
    "research_synopsis": "A study about frozen food consumption and child health."
  }'
```

Search status by user id:

```bash
curl http://127.0.0.1:8000/research-details/user-123/status
```

Search status by topic:

```bash
curl http://127.0.0.1:8000/research-details/by-name/Nutrition%20Study/status
```

## Validation Flow

1. User submits research details through FastAPI or Gradio.
2. `research_service.py` sends the topic to the validator agent.
3. The agent checks:
   - exact matches in MongoDB,
   - semantic matches in ChromaDB,
   - internet context through DuckDuckGo when needed.
4. The LLM returns a decision and final reason.
5. Approved topics are saved in MongoDB and indexed in ChromaDB.
6. Rejected or revision-needed topics are returned with the validator reason.

## Notes

- The Gradio UI calls the controller functions directly from Python.
- A Gradio or Starlette deprecation warning from `.venv/site-packages` can be ignored if the app runs correctly.
- `research_deatils.py` is currently spelled with `deatils`; imports should keep using the existing filename unless it is renamed across the project.
