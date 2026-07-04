"""MongoDB service for storing ResearchDetails payloads.

Environment variables:
    MONGO_URI: Mongo connection string, e.g. mongodb://localhost:27017
    MONGO_DB_NAME: Database name. Defaults to research_db
    MONGO_COLLECTION_NAME: Collection name. Defaults to research_details
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from models.rearch_deatils import ResearchDetails


class ResearchDBService:
    """Service layer responsible for persisting research detail records."""

    def __init__(
        self,
        mongo_uri: str | None = None,
        db_name: str | None = None,
        collection_name: str | None = None,
    ) -> None:
        self.mongo_uri = mongo_uri or os.getenv(
            "MONGO_URI", "mongodb://localhost:27017"
        )
        self.db_name = db_name or os.getenv("MONGO_DB_NAME", "research_db")
        self.collection_name = collection_name or os.getenv(
            "MONGO_COLLECTION_NAME", "research_details"
        )

        self.client: MongoClient = MongoClient(self.mongo_uri)
        self.database: Database = self.client[self.db_name]
        self.collection: Collection = self.database[self.collection_name]

    @staticmethod
    def _model_to_document(payload: ResearchDetails) -> dict[str, Any]:
        """Convert a Pydantic model to a MongoDB-safe dict."""
        if hasattr(payload, "model_dump"):
            # Pydantic v2: mode="json" converts Enum values to strings.
            document = payload.model_dump(mode="json")
        else:
            # Pydantic v1 fallback.
            document = payload.dict()
            if hasattr(document.get("status"), "value"):
                document["status"] = document["status"].value

        now = datetime.now(timezone.utc)
        document["created_at"] = now
        document["updated_at"] = now
        return document

    def save_research_details(self, payload: ResearchDetails) -> dict[str, Any]:
        """Save research details in MongoDB and return the created document."""
        document = self._model_to_document(payload)

        try:
            result = self.collection.insert_one(document)
        except PyMongoError:
            raise

        document["_id"] = str(result.inserted_id)
        return document

    def close(self) -> None:
        """Close the MongoDB connection."""
        self.client.close()
