import asyncio
import re

from pydantic import ValidationError

from models.research_deatils import ResearchDetails, Status

from repos import db_service
from repos.db_service import ResearchDBService
from models.research_deatils import ResearchDetails, ResearchStatusResponse, Status
from guardrails import validate_research_topic


def _validate_llm_result(llm_result: str) -> tuple[str, str]:
    # print(f"LLM Result: {llm_result}")
    print("**" * 50)

    decision_match = re.search(r"(?im)^\s*Decision:\s*(.+?)\s*$", llm_result)
    final_reason_match = re.search(
        r"(?ims)^\s*Final Reason:\s*(.*?)(?=^\s*[A-Z][A-Za-z ]+:\s*|\Z)",
        llm_result,
    )

    decision = decision_match.group(1).strip() if decision_match else ""
    final_reason = final_reason_match.group(1).strip() if final_reason_match else ""

    return decision, final_reason


def create_research_doc(payload: ResearchDetails) -> dict:
    """Accept ResearchDetails JSON, validate it, and save it in MongoDB."""
    try:
        llm_result = result = asyncio.run(
            validate_research_topic.validate_research_topic(payload.topic)
        )
        decision, final_reason = _validate_llm_result(llm_result)
        if Status.APPROVED.value == decision.lower():
            payload.status = Status.UNDER_ANALYSIS
            service = ResearchDBService()
            saved_document = service.save_research_details(payload)
            return {
                "message": "Research details saved successfully.",
                "data": saved_document,
                "validation_result": final_reason,
            }
        else:
            return {
                "message": "Research details not saved. Topic validation failed.",
                "validation_result": final_reason,
            }
    except Exception as e:
        print(f"Error saving research details: {e}")
        return {"message": "Failed to save research details."}


def find_research_status_by_name(topic_name: str) -> dict[str, str] | None:
    service = ResearchDBService()
    topic_lst = []
    resp_data = {}
    try:
        research_status = service.fetch_matching_semantic_topics(topic_name)
        for match in research_status:
            topic_lst.append(match["topic"])

        for topic in topic_lst:
            data = service.get_research_status_by_name(topic)
            if data:
                resp_data[topic] = data

    except Exception as e:
        print(f"Error retrieving research status: {e}")
        return None
    return resp_data


def find_research_status_by_userId(userId: str) -> dict[str, str] | None:
    service = ResearchDBService()
    try:
        research_status = service.get_research_status_by_userid(userId)
        if research_status:
            return research_status
    except Exception as e:
        print(f"Error retrieving research status: {e}")
        return None
    return None


# if __name__ == "__main__":
#     data = {
#         "name": "John Doe",
#         "status": "pending",
#         "is_granted": False,
#         "research_area": "Data Structures",
#         "sources": ["https://www.geeksforgeeks.org/batch/data-science-6?tab=Resources"],
#         "research_synopsis": "Implementation of Data Structure in RAG",
#         "topic": "Implementation of Data Structure in RAG",
#     }
#     # payload = ResearchDetails(**data)
#     # result = create_research_doc(payload)
# print(find_research_status_by_name("Effects of frozen food consumption"))
#     print(find_research_status_by_userId("3x-12a"))
