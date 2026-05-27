import requests
import os
import json
import datetime
from pathlib import Path
import anthropic
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=5)

CATEGORY_LABELS = {
    "where_to_eat": "Where to Eat",
    "into_the_wild": "Into the Wild",
    "gram_worthy_spots": "Gram-Worthy Spots",
    "off_the_beaten_path": "Off the Beaten Path",
}

CACHE_DIR = Path("cache")

REDDIT_HEADERS = {"User-Agent": "cityscout/1.0"}
ADDITIONAL_SUBREDDITS = ["travel", "solotravel"]
POSTS_FROM_CITY_SUB = 10
POSTS_FROM_SEARCH = 5
COMMENTS_PER_POST = 3

PLACE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "description": {"type": "string"},
        },
        "required": ["name", "description"],
    },
}

EXTRACT_TOOL = {
    "name": "extract_recommendations",
    "description": "Save extracted travel recommendations from Reddit posts into 4 categories. Up to 5 entries per category; use an empty array if a category has no clear recommendations.",
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {"type": "string"},
            "categories": {
                "type": "object",
                "properties": {
                    "where_to_eat": PLACE_SCHEMA,
                    "into_the_wild": PLACE_SCHEMA,
                    "gram_worthy_spots": PLACE_SCHEMA,
                    "off_the_beaten_path": PLACE_SCHEMA,
                },
                "required": ["where_to_eat", "into_the_wild", "gram_worthy_spots", "off_the_beaten_path"],
            },
        },
        "required": ["city", "categories"],
    },
}

def log_failure(city, raw_response, error):
    timestamp = datetime.datetime.now().isoformat()
    with open("errors.log", "a") as f:
        f.write(
            f"\n--- {timestamp} ---\n"
            f"city: {city}\n"
            f"error: {error}\n"
            f"raw_response:\n{raw_response}\n"
        )

def is_retryable_error(exc):
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        status = exc.response.status_code
        return status == 429 or status >= 500
    return isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))

reddit_retry = retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception(is_retryable_error),
)

def safe_reddit(fn):
    retrying = reddit_retry(fn)
    def wrapper(*args, **kwargs):
        try:
            return retrying(*args, **kwargs)
        except Exception as e:
            log_failure("reddit", "", f"{fn.__name__}{args} failed: {e}")
            return []
    return wrapper

def cache_key(city):
    return "".join(c if c.isalnum() else "_" for c in city.lower().strip())

def load_from_cache(city):
    path = CACHE_DIR / f"{cache_key(city)}.json"
    if not path.exists():
        return None
    with open(path) as f:
        entry = json.load(f)
    return entry["data"]

def save_to_cache(city, data):
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{cache_key(city)}.json"
    entry = {
        "cached_at": datetime.datetime.now().isoformat(),
        "data": data,
    }
    with open(path, "w") as f:
        json.dump(entry, f, indent=2)

@safe_reddit
def fetch_top_posts(subreddit, limit):
    url = f"https://www.reddit.com/r/{subreddit}/top.json"
    response = requests.get(url, headers=REDDIT_HEADERS, params={"limit": limit, "t": "year"}, timeout=10)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    return [p.get("data", {}) for p in response.json().get("data", {}).get("children", [])]

@safe_reddit
def search_posts(subreddit, query, limit):
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {"q": query, "restrict_sr": 1, "sort": "top", "t": "year", "limit": limit}
    response = requests.get(url, headers=REDDIT_HEADERS, params=params, timeout=10)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    return [p.get("data", {}) for p in response.json().get("data", {}).get("children", [])]

@safe_reddit
def fetch_top_comments(subreddit, post_id, limit):
    url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
    response = requests.get(url, headers=REDDIT_HEADERS, params={"limit": limit, "sort": "top"}, timeout=10)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    data = response.json()
    if len(data) < 2:
        return []
    bodies = []
    for c in data[1].get("data", {}).get("children", []):
        if c.get("kind") != "t1":
            continue
        body = c.get("data", {}).get("body", "").strip()
        if body and body not in ("[deleted]", "[removed]"):
            bodies.append(body)
        if len(bodies) >= limit:
            break
    return bodies

def fetch_reddit_posts(city, subreddit=None):
    sub = subreddit or city
    sections = []

    city_posts = fetch_top_posts(sub, POSTS_FROM_CITY_SUB)
    if city_posts:
        sections.append(f"=== From r/{sub} ===")
        for post in city_posts:
            title = post.get("title", "")
            selftext = post.get("selftext", "")[:200]
            post_id = post.get("id", "")
            sections.append(f"- {title}")
            if selftext:
                sections.append(f"  Body: {selftext}")
            if post_id:
                for comment in fetch_top_comments(sub, post_id, COMMENTS_PER_POST):
                    sections.append(f"  Comment: {comment[:300]}")

    for sub in ADDITIONAL_SUBREDDITS:
        results = search_posts(sub, city, POSTS_FROM_SEARCH)
        if results:
            sections.append(f"\n=== From r/{sub} (search: {city}) ===")
            for post in results:
                title = post.get("title", "")
                selftext = post.get("selftext", "")[:400]
                sections.append(f"- {title}")
                if selftext:
                    sections.append(f"  Body: {selftext}")

    if not sections:
        print(f"Could not fetch data for {city}. Try a different city name.")
        return None

    return "\n".join(sections)

def analyze_with_claude(city, posts_text):
    prompt = f"""You are a travel guide assistant. Based on the following Reddit posts from r/{city}, extract specific place recommendations and call the extract_recommendations tool to save them.

Category meanings:
- where_to_eat: restaurants, food markets, street food
- into_the_wild: parks, nature, outdoor spots
- gram_worthy_spots: cafes, viewpoints, photogenic locations
- off_the_beaten_path: hidden gems, local secrets, lesser known spots

Include up to 5 specific places per category. Each place needs a name and a 1-2 sentence description. If a category has no clear mentions in the posts, use an empty array.

Reddit posts:
{posts_text}
"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "extract_recommendations"},
        messages=[{"role": "user", "content": prompt}],
    )

    tool_use = next((b for b in message.content if b.type == "tool_use"), None)
    if tool_use is None:
        log_failure(city, str(message.content), "No tool_use block in response")
        print(f"\n[error] Claude did not use the extraction tool for {city}. Details written to errors.log.")
        return None

    return tool_use.input

def format_result(data):
    lines = [f"=== CityScout Guide: {data['city']} ==="]
    for key, label in CATEGORY_LABELS.items():
        places = data["categories"].get(key, [])
        lines.append(f"\n{label}\n{'-' * len(label)}")
        if not places:
            lines.append("No recommendations found.")
        else:
            for place in places:
                lines.append(f"• {place['name']} — {place['description']}")
    return "\n".join(lines)

def get_recommendations(city, subreddit=None):
    cached = load_from_cache(city)
    if cached:
        return cached

    posts_text = fetch_reddit_posts(city, subreddit=subreddit)
    if not posts_text:
        return None

    result = analyze_with_claude(city, posts_text)
    if not result:
        return None

    save_to_cache(city, result)
    return result

def main():
    print("\nWelcome to CityScout!")
    print("Discover the best spots in any city, powered by Reddit & AI\n")

    city = input("Enter a city name: ").strip()

    cached = load_from_cache(city)
    if cached:
        print(f"\nUsing cached recommendations for {city}.\n")
        print(format_result(cached))
        return

    print(f"\nFetching recommendations for {city}...\n")

    posts_text = fetch_reddit_posts(city)

    if not posts_text:
        return

    print("Analyzing with AI...\n")
    result = analyze_with_claude(city, posts_text)

    if not result:
        return

    save_to_cache(city, result)
    print(format_result(result))

if __name__ == "__main__":
    main()
