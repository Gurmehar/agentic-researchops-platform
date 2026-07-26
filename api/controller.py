"""FastAPI controller for accepting ResearchDetails JSON and saving it to MongoDB.

Run with:
    uvicorn api.controller:app --reload

Required JSON body example:
{
  "name": "AI Drug Discovery",
  "status": "pending",
  "is_granted": true,
  "research_area": "Artificial Intelligence",
  "sources": ["paper-1", "paper-2"],
  "research_synopsis": "Research synopsis text here."
}

View research status:
    GET /research-details/{research_id}/status
    GET /research-details/by-name/{name}/status
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException, status
from pymongo.errors import PyMongoError
from service import research_service

from models.research_deatils import ResearchDetails, ResearchStatusResponse, Status

router = APIRouter(prefix="/research-details", tags=["Research Details"])
LAST_LOGIN_USER_ID: str | None = None


def _extract_login_user_id(payload: dict) -> str | None:
    if payload.get("id"):
        return str(payload["id"])

    user = payload.get("user")
    if isinstance(user, dict) and user.get("id"):
        return str(user["id"])

    return None


def receive_login_payload(payload: dict) -> dict:
    """Receive login JSON from the UI until a real auth API is added."""
    global LAST_LOGIN_USER_ID

    login_user_id = _extract_login_user_id(payload)
    LAST_LOGIN_USER_ID = login_user_id

    return {
        "status": "HTTP.OK",
        "status_code": 200,
        "message": "Login payload received by controller.",
        "user_id": login_user_id,
        "payload": payload,
    }


def get_logged_in_user_id() -> str:
    return LAST_LOGIN_USER_ID or ""


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_research_details(payload: ResearchDetails) -> dict:
    """Accept ResearchDetails JSON, validate it, and save it in MongoDB."""
    try:

        # saved_document = db_service.save_research_details(payload)
        return research_service.create_research_doc(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save research details in MongoDB: {exc}",
        ) from exc


@router.get("/{researcher_id}/status", response_model=ResearchStatusResponse)
def get_research_status(researcher_id: str) -> dict[str, str]:
    """Return the current status for a research project by MongoDB id."""
    try:

        research_status = research_service.find_research_status_by_userId(researcher_id)
    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get research status from MongoDB: {exc}",
        ) from exc

    if research_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research project not found.",
        )

    return research_status


@router.get("/by-name/{name}/status", response_model=ResearchStatusResponse)
def get_research_status_by_name(name: str) -> dict[str, str]:
    """Return the latest status for a research project by name."""
    try:

        research_status = research_service.find_research_status_by_name(name)
    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get research status from MongoDB: {exc}",
        ) from exc

    if research_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research project not found.",
        )

    return research_status


@router.post("/begin-research", response_model=ResearchStatusResponse)
def begin_research(research_id: str) -> dict[str, str] | None:
    """Initiate the research process for a given research ID."""
    try:
        status_update = research_service.update_topic_for_research(research_id)
        if status_update is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Research can only be started when its status is "
                    f"`{Status.UNDER_ANALYSIS.value}`."
                ),
            )
        if status_update.get("error"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=status_update["error"],
            )
        result = research_service.send_topic_for_research(research_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Research project not found.",
            )
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"],
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to begin research: {exc}",
        ) from exc


@router.delete("/{research_id}/status", response_model=ResearchStatusResponse)
def delete_research(research_id: str) -> dict[str, str]:
    """Delete research from Mongo and ChromeDB."""
    try:
        topic_name = research_service.delete_research_by_id(research_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete research details from MongoDB: {exc}",
        ) from exc

    return {"status": "deleted", "topic_name": topic_name, "research_id": research_id}


app = FastAPI(title="Research Details API")
app.include_router(router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
