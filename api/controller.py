"""FastAPI controller for accepting ResearchDetails JSON and saving it to MongoDB.

Run with:
    uvicorn controller:app --reload

Required JSON body example:
{
  "name": "AI Drug Discovery",
  "status": "pending",
  "is_granted": true,
  "research_area": "Artificial Intelligence",
  "sources": ["paper-1", "paper-2"],
  "research_synopsis": "Research synopsis text here."
}
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException, status
from pymongo.errors import PyMongoError

from repos.db_service import ResearchDBService
from models.rearch_deatils import ResearchDetails

router = APIRouter(prefix="/research-details", tags=["Research Details"])
db_service = ResearchDBService()


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_research_details(payload: ResearchDetails) -> dict:
    """Accept ResearchDetails JSON, validate it, and save it in MongoDB."""
    try:
        saved_document = db_service.save_research_details(payload)
        return {
            "message": "Research details saved successfully.",
            "data": saved_document,
        }
    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save research details in MongoDB: {exc}",
        ) from exc


app = FastAPI(title="Research Details API")
app.include_router(router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
