"""MongoDB service for storing ResearchDetails payloads.

Environment variables:
    MONGO_URI: Mongo connection string, e.g. mongodb://localhost:27017
    MONGO_DB_NAME: Database name. Defaults to research_db
    MONGO_COLLECTION_NAME: Collection name. Defaults to research_details
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError
import chromadb
from langchain_chroma import Chroma

from models.research_deatils import ResearchDetails


class ResearchDBService:
    """Service layer responsible for persisting research detail records."""

    def __init__(
        self,
        mongo_uri: str | None = None,
        db_name: str | None = None,
        collection_name: str | None = None,
        chroma_host: str | None = None,
        chroma_port: str | None = None,
        chroma_collection_name: str | None = None,
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

        self.chroma_host = chroma_host or os.getenv("CHROMA_HOST", "localhost")
        self.chroma_port = chroma_port or os.getenv("CHROMA_PORT", "8000")
        self.chroma_collection_name = chroma_collection_name or os.getenv(
            "CHROMA_COLLECTION_NAME", "research_db"
        )
        self.chroma_client = chromadb.HttpClient(
            host=self.chroma_host, port=self.chroma_port
        )
        self.chroma_collection = self.chroma_client.get_or_create_collection(
            self.chroma_collection_name
        )

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
            self.chroma_collection.add(
                ids=[str(result.inserted_id)],
                documents=[document.get("topic", "")],
                metadatas=[
                    {
                        "research_area": document.get("research_area", ""),
                        "status": document.get("status", ""),
                    }
                ],
            )
        except PyMongoError:
            raise

        document["_id"] = str(result.inserted_id)
        return document

    @staticmethod
    def _status_response_from_document(document: dict[str, Any]) -> dict[str, str]:
        """Build the compact API response for research status lookups."""
        return {
            "id": str(document["_id"]),
            "topic": document["topic"],
            "status": document["status"],
            "name": document["name"],
        }

    def get_research_status_by_userid(self, userid: str) -> dict[str, str] | None:
        """Return research status for a MongoDB document id."""
        doc_dict = {}
        list_doc = self.collection.find(
            {"userId": userid},
            {"topic": 1, "status": 1, "name": 1},
        )
        for doc in list_doc:
            if doc is not None:
                doc_dict[doc["topic"]] = self._status_response_from_document(doc)
        return doc_dict if doc_dict else None

    def get_research_status_by_name(self, topic_name: str) -> dict[str, str] | None:
        """Return the latest research status for a project name."""
        doc_dict = {}
        doc_list = self.collection.find(
            {"topic": topic_name},
            {"topic": 1, "status": 1, "name": 1, "_id": 1},
            sort=[("updated_at", -1), ("created_at", -1)],
        )

        for document in doc_list:
            if document is not None:
                doc_dict[document["topic"]] = self._status_response_from_document(
                    document
                )

        return doc_dict if doc_dict else None

    def fetch_matching_topics(self, topic_name: str):
        """Fetch exact matching topic names from MongoDB."""
        documents = self.collection.find(
            {"topic": topic_name},
            {"topic": 1, "status": 1},
        )
        return [
            {
                "id": str(document["_id"]),
                "topic": document.get("topic", ""),
                "status": document.get("status", ""),
            }
            for document in documents
        ]

    def fetch_matching_approved_topics(self, topic_name: str):
        """Backward-compatible wrapper for the old method name."""
        return self.fetch_matching_topics(topic_name)

    def fetch_matching_semantic_topics(self, topic_name: str) -> list[dict[str, Any]]:
        """Fetch topics from ChromaDB with semantically similar names."""
        result = self.chroma_collection.query(
            query_texts=[topic_name],
            n_results=5,
            include=["metadatas", "documents", "distances"],
        )

        matches = []
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        for topic_id, document, metadata, distance in zip(
            ids, documents, metadatas, distances
        ):
            if (1 - distance) >= 0.7:
                matches.append(
                    {
                        "id": topic_id,
                        "topic": document,
                        "metadata": metadata or {},
                        "distance": distance,
                        "similarity_score": (
                            1 - distance if distance is not None else None
                        ),
                    }
                )
        # print(f"Semantic matches for '{topic_name}': {matches}")
        return matches

    def fetch_matching_sematics_topics(self, topic_name: str) -> list[dict[str, Any]]:
        """Backward-compatible wrapper for the misspelled method name."""
        return self.fetch_matching_semantic_topics(topic_name)

    def close(self) -> None:
        """Close the MongoDB connection."""
        self.client.close()

    def delete_research_by_id(self, research_id) -> str | None:
        """Delete research from MongoDB and ChromaDB by research ID."""
        try:
            # Delete from MongoDB
            document = self.findById(research_id)
            if document is None:
                return None

            result = self.collection.delete_one({"_id": ObjectId(research_id)})
            if result.deleted_count == 0:
                return None

            # Delete from ChromaDB
            var = self.chroma_collection.delete(
                where={"topic": [document.get("topic", "")]}
            )
            print(f"ChromaDB deletion result: {var}")
            return document.get("topic", None)
        except (PyMongoError, InvalidId) as e:
            print(f"Error deleting research: {e}")
            return None

    def findById(self, research_id: str) -> dict[str, Any] | None:
        """Find a research document by its MongoDB ID."""
        try:
            document = self.collection.find_one({"_id": ObjectId(research_id)})
            if document is not None:
                return self._status_response_from_document(document)
        except (PyMongoError, InvalidId) as e:
            print(f"Error finding research by ID: {e}")
            return None
        return None

    def update_doc_status(self, id: str, status: str) -> dict[str, Any] | None:
        """Atomically apply an allowed research workflow status transition."""
        required_current_status = {
            "start_research": "under_analysis",
            "research_in_progress": "start_research",
            "research_failed": "research_in_progress",
        }.get(status)
        if required_current_status is None:
            return None

        try:
            result = self.collection.update_one(
                {
                    "_id": ObjectId(id),
                    "status": required_current_status,
                },
                {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}},
                upsert=False,
            )
            if result.matched_count == 1:
                return self.findById(id)
        except (PyMongoError, InvalidId) as e:
            print(f"Error updating research status: {e}")
            return None
        return None

    def reset_research_for_retry(self, id: str) -> dict[str, Any] | None:
        """Return an unsuccessful active workflow to the retryable UI state."""
        try:
            result = self.collection.update_one(
                {
                    "_id": ObjectId(id),
                    "status": {
                        "$in": ["start_research", "research_in_progress"],
                    },
                },
                {
                    "$set": {
                        "status": "under_analysis",
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
                upsert=False,
            )
            if result.matched_count == 1:
                return self.findById(id)
        except (PyMongoError, InvalidId) as e:
            print(f"Error resetting research for retry: {e}")
            return None
        return None

    def update_research(self, doc: dict) -> dict[str, Any] | None:
        """Update research details of a document by its MongoDB ID."""
        try:
            update_fields = {
                "research_synopsis": doc.get("research_synopsis"),
                "research_area": doc.get("research_area"),
                "sources": doc.get("sources"),
                "status": "research_completed",
                "updated_at": datetime.now(timezone.utc),
            }
            result = self.collection.update_one(
                {"_id": ObjectId(doc["_id"]), "status": "research_in_progress"},
                {"$set": update_fields},
            )
            if result.modified_count > 0:
                return self.findById(doc["_id"])
        except (PyMongoError, InvalidId) as e:
            print(f"Error updating research details: {e}")
            return None
        return None
