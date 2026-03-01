#!/usr/bin/env python3
"""
Add description field to frontmatter of vault files.

Strategy by file type:
- CRM files: "{title} — {type}, {industry}, {status}, {deal_status}"
- Thoughts: first non-empty paragraph after frontmatter, truncated to 150 chars
- MOC: "Map of Content: {topic}, N entries"
- Goals: from first paragraph
- Summaries: "Weekly summary for {week}"
- Other: first paragraph, truncated to 150 chars

Skips:
- daily/ files (don't need descriptions per convention)
- Files that already have description field

Usage:
  uv run vault/.claude/skills/vault-health/scripts/add_descriptions.py          # dry-run
  uv run vault/.claude/skills/vault-health/scripts/add_descriptions.py --apply  # apply
"""

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
VAULT_PATH = SCRIPT_DIR.parents[3]
GRAPH_PATH = VAULT_PATH / ".graph" / "vault-graph.json"

IGNORE_DIRS = {".obsidian", "attachments", ".git", ".graph", ".claude", ".trash"}
IGNORE_PATTERNS = {"backup", ".backup", "archive"}


def load_graph():
    if not GRAPH_PATH.exists():
        print("Error: vault-graph.json not found. Run analyze.py first.")
        sys.exit(1)
    return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))


def parse_frontmatter(content: str) -> dict[str, str]:
    """Extract YAML frontmatter as simple key-value pairs."""
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).split("\n"):
        if ":" in line and not line.strip().startswith("-") and not line.strip().startswith("#"):
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and not value.startswith("[") and not value.startswith("{"):
                fm[key] = value
    return fm


def get_body_after_frontmatter(content: str) -> str:
    """Get content after frontmatter."""
    match = re.match(r"^---\n.*?\n---\n?", content, re.DOTALL)
    if match:
        return content[match.end():]
    return content


def extract_first_paragraph(body: str) -> str:
    """Extract first non-empty, non-heading paragraph from body."""
    lines = body.split("\n")
    paragraph_lines = []
    in_paragraph = False

    for line in lines:
        stripped = line.strip()

        # Skip empty lines before paragraph starts
        if not stripped and not in_paragraph:
            continue

        # Skip headings, callouts, code blocks, links-only lines
        if stripped.startswith(("#", ">", "```", "---", "| ", "- [[", "![")):
            if in_paragraph:
                break
            continue

        if stripped:
            in_paragraph = True
            paragraph_lines.append(stripped)
        elif in_paragraph:
            break

    text = " ".join(paragraph_lines)
    # Remove wikilinks: [[path|text]] → text, [[path]] → path
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    # Remove markdown formatting
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def truncate(text: str, max_len: int = 150) -> str:
    """Truncate text to max_len on word boundary."""
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    # Find last space
    last_space = truncated.rfind(" ")
    if last_space > max_len // 2:
        truncated = truncated[:last_space]
    return truncated.rstrip(".,;: ") + "..."


def generate_description(rel_path: str, content: str, fm: dict) -> str | None:
    """Generate a description for a file based on its type and content."""

    # CRM files (business/crm/, projects/crm/)
    if any(rel_path.startswith(p) for p in ("business/crm/", "projects/crm/")):
        # Extract title from H1 or filename
        title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else Path(rel_path).stem.replace("-", " ").title()

        parts = []
        if fm.get("type"):
            parts.append(fm["type"])
        if fm.get("industry"):
            parts.append(fm["industry"])
        if fm.get("status"):
            parts.append(fm["status"])
        if fm.get("deal_status"):
            parts.append(fm["deal_status"])
        if fm.get("region"):
            parts.append(fm["region"])

        if parts:
            return truncate(f"{title} — {', '.join(parts)}")
        return truncate(f"{title} — CRM record")

    # Projects files
    if rel_path.startswith("projects/"):
        title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else Path(rel_path).stem.replace("-", " ").title()

        parts = []
        if fm.get("type"):
            parts.append(fm["type"])
        if fm.get("industry"):
            parts.append(fm["industry"])
        if fm.get("status"):
            parts.append(fm["status"])
        if parts:
            return truncate(f"{title} — {', '.join(parts)}")

        body = get_body_after_frontmatter(content)
        para = extract_first_paragraph(body)
        if para:
            return truncate(para)
        return truncate(f"{title} — Projects")

    # MOC files
    if rel_path.startswith("MOC/"):
        topic = Path(rel_path).stem.removeprefix("MOC-").replace("-", " ").title()
        link_count = content.count("[[")
        return f"Map of Content: {topic}, {link_count} entries"

    # Thoughts
    if rel_path.startswith("thoughts/"):
        body = get_body_after_frontmatter(content)
        para = extract_first_paragraph(body)
        if para:
            return truncate(para)
        # Fallback: use filename
        stem = Path(rel_path).stem
        # Remove date prefix if present
        stem = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)
        return stem.replace("-", " ").capitalize()

    # Goals
    if rel_path.startswith("goals/"):
        body = get_body_after_frontmatter(content)
        para = extract_first_paragraph(body)
        if para:
            return truncate(para)
        return f"Goal: {Path(rel_path).stem.replace('-', ' ')}"

    # Summaries
    if rel_path.startswith("summaries/"):
        stem = Path(rel_path).stem
        week_match = re.search(r"(\d{4}-W\d{2})", stem)
        if week_match:
            return f"Weekly summary for {week_match.group(1)}"
        return f"Summary: {stem.replace('-', ' ')}"

    # Contacts
    if rel_path.startswith("contacts/"):
        body = get_body_after_frontmatter(content)
        para = extract_first_paragraph(body)
        if para:
            return truncate(para)
        return f"Contacts: {Path(rel_path).stem.replace('-', ' ')}"

    # _index files
    if Path(rel_path).stem == "_index":
        parent = Path(rel_path).parent.name
        return f"Index and entry point for {parent}"

    # MEMORY.md
    if Path(rel_path).name == "MEMORY.md":
        return "Long-term memory and key decisions"

    # Default: first paragraph
    body = get_body_after_frontmatter(content)
    para = extract_first_paragraph(body)
    if para:
        return truncate(para)

    return None


def add_description_to_frontmatter(content: str, description: str) -> str:
    """Add description field to frontmatter."""
    # Escape quotes in description
    safe_desc = description.replace('"', '\\"')

    if content.startswith("---\n"):
        match = re.match(r"^(---\n)(.*?)(\n---)", content, re.DOTALL)
        if match:
            before = match.group(1)
            fm_body = match.group(2)
            after = match.group(3)
            rest = content[match.end():]
            return f'{before}description: "{safe_desc}"\n{fm_body}{after}{rest}'
    else:
        # Create minimal frontmatter
        return f'---\ndescription: "{safe_desc}"\n---\n{content}'

    return content


def main():
    apply = "--apply" in sys.argv

    graph = load_graph()
    nodes = graph.get("nodes", {})

    # Get all non-daily files
    all_files = [
        f for f in VAULT_PATH.rglob("*.md")
        if not any(d in f.parts for d in IGNORE_DIRS)
        and not any(p in str(f) for p in IGNORE_PATTERNS)
    ]

    print(f"Total markdown files: {len(all_files)}")
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print()

    added = 0
    skipped_daily = 0
    already_has = 0
    no_description = 0
    errors = 0

    for file_path in sorted(all_files):
        rel_path = str(file_path.relative_to(VAULT_PATH))

        # Skip daily files
        if rel_path.startswith("daily/"):
            skipped_daily += 1
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            errors += 1
            continue

        # Check if already has description
        fm = parse_frontmatter(content)
        if fm.get("description"):
            already_has += 1
            continue

        # Also check raw frontmatter for description: field
        fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if fm_match and "description:" in fm_match.group(1):
            already_has += 1
            continue

        description = generate_description(rel_path, content, fm)
        if not description:
            no_description += 1
            if "--verbose" in sys.argv:
                print(f"  NO DESC: {rel_path}")
            continue

        print(f"  {rel_path}: \"{description[:80]}{'...' if len(description) > 80 else ''}\"")
        added += 1

        if apply:
            new_content = add_description_to_frontmatter(content, description)
            file_path.write_text(new_content, encoding="utf-8")

    non_daily = len(all_files) - skipped_daily
    coverage = (already_has + added) / max(non_daily, 1) * 100

    print(f"\n{'='*50}")
    print(f"Non-daily files: {non_daily}")
    print(f"Already had description: {already_has}")
    print(f"Descriptions added: {added}")
    print(f"Could not generate: {no_description}")
    print(f"Errors: {errors}")
    print(f"Projected coverage: {coverage:.1f}%")
    if apply:
        print(f"Files modified: {added}")


if __name__ == "__main__":
    main()
