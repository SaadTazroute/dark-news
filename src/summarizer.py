"""SummarizerAgent — generates a Digest from ranked SignalItems using Claude via Bedrock."""

import json
import logging
from datetime import date
from pathlib import Path
from typing import List

import boto3
from jinja2 import Environment, FileSystemLoader

from src.models import Digest, SignalItem
from src.retry import with_retry

logger = logging.getLogger(__name__)

SOURCE_LABELS = {
    "arxiv": "Arxiv Preprints",
    "github": "GitHub Activity",
    "huggingface": "HuggingFace Models",
    "reddit": "Reddit Signals",
    "aws_changelog": "AWS Changelog",
}

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def group_by_source(items: List[SignalItem]) -> dict:
    """Partition SignalItems by source_type."""
    groups: dict = {}
    for item in items:
        groups.setdefault(item.source_type, []).append(item)
    return groups


def build_prompt(groups: dict) -> str:
    """Construct a Claude prompt with nerd-tone, consultant-angle instructions."""
    lines = [
        "You are a sharp, opinionated AI/cloud intelligence analyst writing for a technically sophisticated audience.",
        "Your tone is nerd-tone, consultant-angle: precise, insightful, slightly irreverent — no fluff, no hype.",
        "",
        "Below are today's high-signal items grouped by source. For each group, write a brief editorial commentary",
        "(2-3 sentences) that frames the significance of the group as a whole. For each individual item, write a",
        "'Why this matters' blurb (1-2 sentences) that explains the practical or strategic implication.",
        "",
        "Return ONLY valid JSON in this exact shape — no markdown fences, no extra text:",
        '{',
        '  "groups": [',
        '    {',
        '      "source_type": "<source_type>",',
        '      "source_label": "<human label>",',
        '      "commentary": "<2-3 sentence editorial>",',
        '      "items": [',
        '        {"title": "...", "summary": "...", "why_it_matters": "...", "url": "..."}',
        '      ]',
        '    }',
        '  ]',
        '}',
        "",
        "Here are the items:",
        "",
    ]

    for source_type, source_items in groups.items():
        label = SOURCE_LABELS.get(source_type, source_type.replace("_", " ").title())
        lines.append(f"## {label} ({source_type})")
        for item in source_items:
            lines.append(f"- Title: {item.title}")
            lines.append(f"  Summary: {item.summary}")
            lines.append(f"  URL: {item.url}")
        lines.append("")

    return "\n".join(lines)


@with_retry(max_retries=2, base_wait=2, max_wait=30)
def invoke_claude(prompt: str, aws_region: str = "us-east-1") -> str:
    """Call Bedrock Claude 3.5 Sonnet and return the response text."""
    bedrock = boto3.client("bedrock-runtime", region_name=aws_region)
    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def render_templates(content: str, items: List[SignalItem]) -> Digest:
    """Parse Claude JSON response and render Jinja2 templates into a Digest."""
    parsed = json.loads(content)
    # Rename 'items' key to 'signals' to avoid conflict with Jinja2/Python dict .items()
    raw_groups = parsed.get("groups", [])
    groups = []
    for g in raw_groups:
        g["signals"] = g.pop("items", [])
        groups.append(g)

    today = date.today().isoformat()
    sources_summary = {g["source_type"]: len(g.get("signals", [])) for g in groups}
    total_items = sum(sources_summary.values())

    context = {
        "date": today,
        "groups": groups,
        "total_items": total_items,
        "pipeline_date": today,
    }

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
    plain_text = env.get_template("digest_plain.j2").render(**context)
    html = env.get_template("digest_html.j2").render(**context)

    return Digest(
        date=today,
        plain_text=plain_text,
        html=html,
        item_count=total_items,
        sources_summary=sources_summary,
    )


class SummarizerAgent:
    """Generates a Digest from ranked SignalItems using Claude via Bedrock."""

    def summarize(self, items: List[SignalItem], config: dict) -> Digest:
        """Full pipeline: group → prompt → invoke Claude → render templates."""
        aws_region = config.get("aws_region", "us-east-1")
        groups = group_by_source(items)

        if not groups:
            logger.warning("SummarizerAgent: no items to summarize")
            today = date.today().isoformat()
            return Digest(date=today, plain_text="No items.", html="<p>No items.</p>", item_count=0, sources_summary={})

        prompt = build_prompt(groups)
        logger.info(f"SummarizerAgent: invoking Claude for {len(items)} items across {len(groups)} sources")
        content = invoke_claude(prompt, aws_region=aws_region)
        return render_templates(content, items)
