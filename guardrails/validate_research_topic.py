import asyncio
from agents import Agent, Runner, trace, function_tool
from dotenv import load_dotenv
import requests
from guardrails import prompts
from repos.db_service import ResearchDBService

load_dotenv(override=True)

db_service = ResearchDBService()


@function_tool
def _fetch_matching_topics(topic_name: str) -> list[dict]:
    """Fetch MongoDB topics with exact matching names."""
    return db_service.fetch_matching_topics(topic_name)


@function_tool
def _fetch_matching_semantics(topic_name: str) -> list[dict]:
    """Fetch ChromaDB topics with semantically similar names."""
    return db_service.fetch_matching_semantic_topics(topic_name)


@function_tool
def _search_internet_for_research_topic(topic: str) -> dict:
    """Search the internet for information about a research topic."""
    url = "https://api.duckduckgo.com/"
    params = {
        "q": topic,
        "format": "json",
        "no_html": 1,
        "skip_disambig": 1,
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()

    results = []

    if data.get("AbstractText"):
        results.append(
            {
                "title": data.get("Heading"),
                "snippet": data.get("AbstractText"),
                "url": data.get("AbstractURL"),
                "source": data.get("AbstractSource"),
            }
        )

    for item in data.get("RelatedTopics", [])[:5]:
        if "Text" in item:
            results.append(
                {
                    "title": item.get("Text", "").split(" - ")[0],
                    "snippet": item.get("Text"),
                    "url": item.get("FirstURL"),
                    "source": "DuckDuckGo",
                }
            )

    return {
        "topic": topic,
        "results_found": len(results),
        "results": results,
    }


async def validate_research_topic(topic: str) -> str:
    agent_prompt = prompts.TOPIC_VALIDATION_PROMPT.format(topic_name=topic)
    agent = Agent(
        name="Research Topic Validator",
        instructions=agent_prompt,
        model="gpt-4.1-mini",
        tools=[
            _fetch_matching_topics,
            _fetch_matching_semantics,
            _search_internet_for_research_topic,
        ],
    )
    with trace("validate topic name"):
        runner = await Runner.run(agent, topic)
        return runner.final_output
