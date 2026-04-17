# ── 1. IMPORTS & CONFIG ─────────────────────────────────────
import requests

SEARXNG_URL = "http://localhost:8080/search"


# ── 2. SEARCH ───────────────────────────────────────────────
def searxng_search(query: str, max_results: int = 5, categories: str = "general", language: str = "auto") -> list:
    """Query local SearXNG aggregator. Hits Google, Bing, Baidu, Yandex, etc. in parallel."""
    try:
        params = {"q": query, "format": "json", "categories": categories, "language": language}
        response = requests.get(SEARXNG_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "engine": r.get("engine", "unknown"),
            }
            for r in data.get("results", [])[:max_results]
        ]
    except requests.exceptions.ConnectionError:
        return [{"error": "SearXNG is not running. Start it with: docker compose up -d"}]
    except Exception as e:
        return [{"error": f"SearXNG search failed: {str(e)}"}]


# ── 3. FORMATTED OUTPUT ─────────────────────────────────────
def searxng_search_formatted(query: str, max_results: int = 5) -> str:
    """Formatted string output for agent consumption."""
    results = searxng_search(query, max_results)

    if results and "error" in results[0]:
        return f"SearXNG error: {results[0]['error']}"
    if not results:
        return f"No results for '{query}'."

    output = f"SearXNG results for '{query}' (aggregated from multiple engines):\n\n"
    for i, r in enumerate(results, 1):
        output += f"{i}. [{r['engine']}] {r['title']}\n   URL: {r['url']}\n   {r['content'][:250]}\n\n"
    return output
