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


from models.research_deatils import ResearchDetails, ResearchStatusResponse
from service import research_service

router = APIRouter(prefix="/research-details", tags=["Research Details"])


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


app = FastAPI(title="Research Details API")
app.include_router(router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
