"""
Daily Digest — autonomous research agent using Claude + Brave Search.

Reads topics from config.yaml, has Claude research each one via web search,
then sends a formatted HTML digest email via Gmail SMTP.
"""

import datetime
import json
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
import markdown
import requests
import yaml
from dotenv import load_dotenv

# ── Load environment variables ─────────────────────────────────────────────────
# load_dotenv() is a no-op when .env is absent (e.g. in GitHub Actions),
# so the same script works both locally and in CI without branching.
load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
BRAVE_API_KEY = os.environ["BRAVE_API_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")
DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"

# ── Load config ────────────────────────────────────────────────────────────────
with open("config.yaml") as f:
    config = yaml.safe_load(f)

digest_title = config["digest"]["title"]
topics = config["topics"]
recipient = RECIPIENT_EMAIL or config["digest"].get("recipient_email", "")

if not recipient and not DEBUG_MODE:
    print("ERROR: No recipient email set. Set RECIPIENT_EMAIL env var or add "
          "recipient_email under digest: in config.yaml.", file=sys.stderr)
    sys.exit(1)

# ── Brave Search ───────────────────────────────────────────────────────────────
def brave_web_search(query: str, count: int = 8) -> list[dict]:
    """Call Brave Search API and return normalized results."""
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY,
    }
    params = {
        "q": query,
        "count": min(count, 10),
        "freshness": "pd",          # prefer results from the past day
        "text_decorations": False,
    }
    response = requests.get(url, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    results = []
    for r in data.get("web", {}).get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "description": r.get("description", ""),
        })
    return results


# ── Anthropic tool definition ──────────────────────────────────────────────────
WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": (
        "Search the web for current news and information. "
        "Call this tool multiple times with different queries to gather "
        "comprehensive coverage of a topic. Prefer recent, authoritative sources."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query string",
            },
            "count": {
                "type": "integer",
                "description": "Number of results to return (1-10, default 8)",
                "default": 8,
            },
        },
        "required": ["query"],
    },
}


# ── Agentic research loop ──────────────────────────────────────────────────────
def research_topic(client: anthropic.Anthropic, topic: dict) -> str:
    """
    Run the Claude agentic tool-use loop for one topic.
    Claude autonomously decides how many searches to make, then synthesizes
    a markdown summary. Returns the final markdown string.
    """
    today = datetime.date.today().strftime("%B %d, %Y")

    system_prompt = f"""You are a research assistant creating a daily briefing for {today}.
Your job is to research the topic "{topic['name']}" and write a concise, \
informative summary suitable for a busy professional's morning digest.

Topic focus: {topic['description']}

Research strategy:
- Make 2-4 targeted web searches to find today's most relevant developments.
- Prioritize news from the last 48 hours where available.
- Include specific names, numbers, and facts — not vague summaries.
- After gathering enough information, write your summary WITHOUT calling any more tools.

Output format (markdown only — no preamble, no "Here is the summary"):
- Use bullet points (- ) for 3-5 key developments.
- Be specific: include names, numbers, and dates.
- End with a "### Sources" subsection listing 2-3 URLs as markdown links,
  using only URLs that actually appeared in your search results."""

    messages = [
        {
            "role": "user",
            "content": f"Research and summarize today's top developments for: {topic['name']}",
        }
    ]

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_prompt,
            tools=[WEB_SEARCH_TOOL],
            messages=messages,
        )

        # Always append the assistant turn before processing
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Extract the final text block
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        if response.stop_reason == "tool_use":
            # Collect all tool calls from this turn and return all results at once
            tool_results = []
            for block in response.content:
                if block.type == "tool_use" and block.name == "web_search":
                    try:
                        results = brave_web_search(
                            query=block.input["query"],
                            count=block.input.get("count", 8),
                        )
                        content = json.dumps(results)
                    except requests.RequestException as exc:
                        content = json.dumps({"error": str(exc)})

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content,
                    })

            messages.append({"role": "user", "content": tool_results})
            # Loop — Claude will now process the search results


# ── HTML email building ────────────────────────────────────────────────────────
def topic_to_html(topic_name: str, markdown_content: str) -> str:
    html_body = markdown.markdown(markdown_content, extensions=["nl2br"])
    return f"""
    <div style="margin-bottom:36px; border-left:4px solid #4A90E2; padding-left:16px;">
      <h2 style="color:#1a1a2e; font-family:Georgia,serif; margin:0 0 10px;">
        {topic_name}
      </h2>
      <div style="color:#333; font-family:Arial,sans-serif; line-height:1.7; font-size:15px;">
        {html_body}
      </div>
    </div>"""


def build_email_html(title: str, date_str: str, topic_sections: list[str]) -> str:
    sections_html = "\n".join(topic_sections)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="background:#f0f2f5; margin:0; padding:24px 0;">
  <div style="max-width:680px; margin:0 auto; background:#ffffff;
               border-radius:10px; overflow:hidden;
               box-shadow:0 2px 12px rgba(0,0,0,0.10);">

    <!-- Header -->
    <div style="background:#1a1a2e; padding:28px 36px;">
      <h1 style="color:#ffffff; font-family:Georgia,serif; margin:0; font-size:26px;
                 letter-spacing:-0.5px;">
        {title}
      </h1>
      <p style="color:#9ca3af; font-family:Arial,sans-serif; margin:6px 0 0;
                font-size:13px;">
        {date_str}
      </p>
    </div>

    <!-- Body -->
    <div style="padding:36px;">
      {sections_html}
    </div>

    <!-- Footer -->
    <div style="background:#f8f9fa; padding:16px 36px; border-top:1px solid #e5e7eb;
                text-align:center;">
      <p style="color:#9ca3af; font-size:12px; font-family:Arial,sans-serif; margin:0;">
        Researched by Claude (claude-sonnet-4-6) &middot; Brave Search
      </p>
    </div>
  </div>
</body>
</html>"""


# ── Gmail SMTP sending ─────────────────────────────────────────────────────────
def send_email(subject: str, html_body: str, to: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, to, msg.as_string())


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today_str = datetime.date.today().strftime("%B %d, %Y")
    subject = f"{digest_title} — {today_str}"

    print(f"Starting daily digest: {subject}")
    print(f"Topics: {[t['name'] for t in topics]}\n")

    topic_sections = []
    for topic in topics:
        print(f"  Researching: {topic['name']} ...", end=" ", flush=True)
        summary_md = research_topic(client, topic)
        topic_sections.append(topic_to_html(topic["name"], summary_md))
        print("done")

    html = build_email_html(digest_title, today_str, topic_sections)

    if DEBUG_MODE:
        print("\n--- DEBUG: HTML output (email not sent) ---")
        print(html)
        print("--- END DEBUG ---")
    else:
        print(f"\nSending digest to {recipient} ...", end=" ", flush=True)
        send_email(subject, html, recipient)
        print("sent!")


if __name__ == "__main__":
    main()
