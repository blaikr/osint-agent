# ── 1. IMPORTS & SETUP ──────────────────────────────────────
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import asyncio
import requests
from dotenv import load_dotenv
from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from ddgs import DDGS
from crawl4ai import AsyncWebCrawler

from prompts import OSINT_SYSTEM_PROMPT
from memory import save_investigation, search_memory, list_all_subjects
from translator import translate_target, translate_content_to_english
from searxng_client import searxng_search_formatted, searxng_search
from geo_tools import get_location_intelligence

load_dotenv()


# ── 2. NON-WESTERN TARGET DETECTION ─────────────────────────
def detect_needs_multilingual(query: str) -> tuple[bool, list]:
    query_lower = query.lower()
    regions = []

    east_asian = ['xi jinping', 'china', 'chinese', 'taiwan', 'taiwanese',
                  'japan', 'japanese', 'korea', 'korean', 'kim jong',
                  'beijing', 'shanghai', 'hong kong', 'tokyo', 'seoul']
    middle_east = ['bin salman', 'mbs', 'saudi', 'iran', 'iranian',
                   'Lebanon', 'arab', 'netanyahu', 'arabic', 'dubai',
                   'uae', 'egypt', 'syria', 'iraq', 'erdogan', 'turkey', 'turkish']
    europe = ['putin', 'russia', 'russian', 'ukraine', 'ukrainian',
              'zelensky', 'kremlin', 'moscow', 'kyiv', 'medvedev']
    south_asia = ['modi', 'india', 'indian', 'pakistani', 'pakistan']

    if any(kw in query_lower for kw in east_asian): regions.append('east_asia')
    if any(kw in query_lower for kw in middle_east): regions.append('middle_east')
    if any(kw in query_lower for kw in europe): regions.append('europe')
    if any(kw in query_lower for kw in south_asia): regions.append('south_asia')

    return (len(regions) > 0, regions)


# ── 3. SEARCH TOOLS ─────────────────────────────────────────
@tool
def web_search(query: str) -> str:
    """Search the general web for any topic. Use this for people, companies, places, events, background info."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return f"No results found for {query}."
        output = f"Web search results for {query}:\n\n"
        for i, r in enumerate(results, 1):
            output += f"{i}. {r.get('title', 'No title')}\n   URL: {r.get('href', '')}\n   {r.get('body', '')}\n\n"
        return output
    except Exception as e:
        return f"Error during web search: {str(e)}"


@tool
def deep_web_search(query: str) -> str:
    """Powerful web search querying multiple engines in parallel (Google, Bing, Baidu, Yandex). PRIMARY search tool with strong international coverage."""
    return searxng_search_formatted(query, max_results=8)


@tool
def search_news(query: str) -> str:
    """Search for recent news articles about a given topic."""
    api_key = os.getenv("NEWSAPI_KEY")
    url = f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt&pageSize=5&apiKey={api_key}"
    response = requests.get(url)
    data = response.json()

    if data.get("status") != "ok":
        return f"Error searching news: {data.get('message', 'unknown error')}"

    articles = data.get("articles", [])
    if not articles:
        return f"No articles found for {query}."

    result = f"Found {len(articles)} recent articles about {query}:\n\n"
    for i, article in enumerate(articles, 1):
        title = article.get("title", "No title")
        source = article.get("source", {}).get("name", "Unknown")
        description = article.get("description", "No description")
        published = article.get("publishedAt", "")[:10]
        result += f"{i}. [{source}, {published}] {title}\n   {description}\n\n"
    return result


# ── 4. SCRAPING TOOLS ───────────────────────────────────────
@tool
def scrape_page(url: str) -> str:
    """Scrape and read the full content of any webpage. Use after search to read articles in detail."""
    try:
        async def _scrape():
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url=url)
                return result.markdown

        content = asyncio.run(_scrape())
        if len(content) > 4000:
            content = content[:4000] + "\n\n[...content truncated...]"
        return f"Content from {url}:\n\n{content}"
    except Exception as e:
        return f"Error scraping page: {str(e)}"


@tool
def translate_and_read(url: str, source_language: str = "auto") -> str:
    """Scrape a foreign-language webpage and translate its content to English."""
    scrape_result = scrape_page.invoke({"url": url})
    if "Error" in scrape_result[:50]:
        return scrape_result
    content = scrape_result.split("Content from", 1)[-1]
    content = content.split(":\n\n", 1)[-1] if ":\n\n" in content else content
    translated = translate_content_to_english(content[:4000], source_language)
    return f"=== TRANSLATED CONTENT FROM {url} (source: {source_language}) ===\n\n{translated}"


# ── 5. MULTILINGUAL TOOLS ───────────────────────────────────
LANG_CODES = {
    "arabic": "ar", "persian": "fa", "hebrew": "he", "turkish": "tr",
    "russian": "ru", "chinese_simplified": "zh-CN", "chinese_traditional": "zh-TW",
    "japanese": "ja", "korean": "ko", "spanish": "es", "french": "fr",
    "german": "de", "portuguese": "pt", "italian": "it", "ukrainian": "uk", "hindi": "hi",
}


@tool
def multilingual_search(target: str, regions: str = "all") -> str:
    """Search for a target across multiple languages using SearXNG with regional engines. Use for non-Western targets.

    regions: "all", "middle_east", "east_asia", "europe", "south_asia"
    """
    region_list = [r.strip() for r in regions.split(",")]
    translations = translate_target(target, region_list)
    if "error" in translations:
        return f"Translation failed: {translations['error']}"

    out = [f"=== MULTILINGUAL SEARCH (via SearXNG): {target} ===\n",
           f"Searching regional engines for {len(translations)} languages...\n"]

    for language, translated_query in translations.items():
        lang_code = LANG_CODES.get(language, "auto")
        try:
            results = searxng_search(translated_query, max_results=3, language=lang_code)
            if results and "error" not in results[0]:
                out.append(f"\n--- {language.upper()} (query: {translated_query}) ---")
                for r in results:
                    out.append(f"  • [{r['engine']}] {r['title']}")
                    out.append(f"    {r['url']}")
                    out.append(f"    {r['content'][:200]}")
            else:
                out.append(f"\n--- {language.upper()}: no results ---")
        except Exception as e:
            out.append(f"\n--- {language.upper()}: search failed ({str(e)[:100]}) ---")

    return "\n".join(out)


@tool
def get_target_translations(target: str, regions: str = "all") -> str:
    """Get native-script translations of a target name/topic across multiple languages."""
    region_list = [r.strip() for r in regions.split(",")]
    translations = translate_target(target, region_list)
    if "error" in translations:
        return f"Translation failed: {translations['error']}"
    output = f"Translations of '{target}':\n\n"
    for lang, translated in translations.items():
        output += f"  • {lang}: {translated}\n"
    return output


# ── 6. MEMORY TOOLS ─────────────────────────────────────────
@tool
def recall_memory(query: str) -> str:
    """Search past investigations in long-term memory. Call FIRST before any new investigation to check for prior findings."""
    return search_memory(query)


@tool
def list_memory() -> str:
    """List all subjects that have ever been investigated."""
    return list_all_subjects()


# ── 7. GEOSPATIAL TOOLS ─────────────────────────────────────
@tool
def location_intelligence(location: str) -> str:
    """Get satellite imagery and geographic intelligence for any location (workplace, institution, city, address).

    Examples: "University of Texas at Dallas", "SpaceX Boca Chica Texas", "Al-Nassr FC stadium Riyadh"
    Returns formatted address, coordinates, classification, and satellite image URLs at three zoom levels.
    """
    return get_location_intelligence(location)


# ── 8. TOOL REGISTRY ────────────────────────────────────────
tools = [
    search_news,
    web_search,
    deep_web_search,
    scrape_page,
    recall_memory,
    list_memory,
    multilingual_search,
    translate_and_read,
    get_target_translations,
    location_intelligence,
]


# ── 9. LLM & GRAPH ──────────────────────────────────────────
llm = ChatAnthropic(model="claude-haiku-4-5", temperature=0.2)
llm_with_tools = llm.bind_tools(tools)


class State(TypedDict):
    messages: Annotated[list, add_messages]


def agent_node(state: State):
    messages = [{"role": "system", "content": OSINT_SYSTEM_PROMPT}] + list(state["messages"])
    try:
        return {"messages": [llm_with_tools.invoke(messages)]}
    except Exception as e:
        return {"messages": [{"role": "assistant", "content": f"Error in agent reasoning: {str(e)}. Please rephrase your query."}]}


graph_builder = StateGraph(State)
graph_builder.add_node("agent", agent_node)
graph_builder.add_node("tools", ToolNode(tools))
graph_builder.add_edge(START, "agent")
graph_builder.add_conditional_edges("agent", tools_condition)
graph_builder.add_edge("tools", "agent")
graph = graph_builder.compile()


# ── 10. INVESTIGATION PIPELINE ──────────────────────────────
MEMORY_SHORTCUTS = [
    "what's in memory", "whats in memory", "what is in memory",
    "what have we investigated", "list memory", "show memory",
    "what do we know so far", "what have i investigated"
]


def _build_initial_messages(user_input: str) -> list:
    needs_ml, regions = detect_needs_multilingual(user_input)
    messages = [{"role": "user", "content": user_input}]

    if not needs_ml:
        return messages

    print(f"🌍 Non-Western target detected. Running multilingual search for regions: {regions}")
    ml_result = multilingual_search.invoke({"target": user_input, "regions": ",".join(regions)})
    print(f"[✓ Multilingual search complete — {len(ml_result)} chars of foreign-language context loaded]")

    messages.insert(0, {
        "role": "system",
        "content": f"""CRITICAL: A multilingual search has ALREADY been executed before this investigation. Results below. Do NOT call multilingual_search yourself.

Your workflow:
1. Use web_search, scrape_page, search_news for additional English context.
2. Build INTERNATIONAL COVERAGE section using ONLY the results below.
3. NEVER invent foreign-language sources not present below.
4. Only cite URLs from tool results.

ACTUAL MULTILINGUAL SEARCH RESULTS:
===================================
{ml_result}
===================================
"""
    })
    return messages


def _should_save(final_response: str, tool_calls: list) -> bool:
    if "INTELLIGENCE REPORT" not in final_response or len(final_response) < 500:
        return False
    if not tool_calls:
        return False
    memory_only = all(tc.get('name') in ('recall_memory', 'list_memory') for tc in tool_calls)
    return not memory_only


def _extract_subject(final_response: str) -> str:
    for line in final_response.split("\n"):
        if "INTELLIGENCE REPORT:" in line:
            return line.split("INTELLIGENCE REPORT:")[-1].strip().strip("#").strip()
    return "Unknown"


def investigate(query: str) -> dict:
    """Run one investigation. Returns final response, tool calls, and saved subject (if any). Used by the UI."""
    initial_messages = _build_initial_messages(query)
    result = graph.invoke({"messages": initial_messages}, config={"recursion_limit": 50})
    final_response = result['messages'][-1].content

    tool_calls = []
    for msg in result['messages']:
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append({'name': tc.get('name', 'unknown'), 'args': tc.get('args', {})})

    saved_subject = None
    if _should_save(final_response, tool_calls):
        saved_subject = _extract_subject(final_response)
        save_investigation(subject=saved_subject, report=final_response, query=query)

    return {'response': final_response, 'tool_calls': tool_calls, 'saved_subject': saved_subject}


def run():
    while True:
        user_input = input("Message: ")
        if user_input == "exit":
            break

        if any(phrase in user_input.lower().strip() for phrase in MEMORY_SHORTCUTS):
            print(list_all_subjects())
            continue

        result = investigate(user_input)
        print(f"Assistant: {result['response']}")
        if result['saved_subject']:
            print(f"\n[✓ Investigation saved to memory: {result['saved_subject']}]")


if __name__ == "__main__":
    run()
