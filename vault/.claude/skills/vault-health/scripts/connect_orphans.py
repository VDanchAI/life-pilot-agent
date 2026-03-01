#!/usr/bin/env python3
"""
Connect orphan and weakly-connected files by adding related links to hub files.

Strategy:
- business/crm/* → related: ["[[business/_index]]"]
- projects/crm/* → related: ["[[projects/_index]]"]
- daily/* (old) → skip (expected orphans)
- templates/* → skip
- projects/* → related: ["[[projects/_index]]"]
- business/* → related: ["[[business/_index]]"]
- thoughts/* → related: ["[[MEMORY]]"]
- Other → related: ["[[MEMORY]]"]

Also processes weakly_connected files (total_links < 2) with same logic.

Usage:
  uv run vault/.claude/skills/vault-health/scripts/connect_orphans.py          # dry-run
  uv run vault/.claude/skills/vault-health/scripts/connect_orphans.py --apply  # apply
"""

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
VAULT_PATH = SCRIPT_DIR.parents[3]
GRAPH_PATH = VAULT_PATH / ".graph" / "vault-graph.json"

# Hub mapping by path prefix
HUB_MAP = [
    ("business/crm/", '[[business/_index]]'),
    ("projects/crm/", '[[projects/_index]]'),
    ("business/network/", '[[business/_index]]'),
    ("business/events/", '[[business/_index]]'),
    ("business/", '[[business/_index]]'),
    ("projects/clients/", '[[projects/_index]]'),
    ("projects/leads/", '[[projects/_index]]'),
    ("projects/", '[[projects/_index]]'),
    ("thoughts/", '[[MEMORY]]'),
    ("goals/", '[[MEMORY]]'),
    ("contacts/", '[[MEMORY]]'),
    ("MOC/", '[[MEMORY]]'),
    ("summaries/", '[[MEMORY]]'),
    (".session/", '[[MEMORY]]'),
]

SKIP_PREFIXES = ("daily/", "templates/", ".claude/", ".graph/")


def load_graph():
    if not GRAPH_PATH.exists():
        print("Error: vault-graph.json not found. Run analyze.py first.")
        sys.exit(1)
    return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))


def get_hub_for_path(rel_path: str) -> str | None:
    """Determine the hub link for a given file path."""
    if any(rel_path.startswith(p) for p in SKIP_PREFIXES):
        return None
    for prefix, hub in HUB_MAP:
        if rel_path.startswith(prefix):
            return hub
    return '[[MEMORY]]'


def has_frontmatter(content: str) -> bool:
    """Check if content has YAML frontmatter."""
    return content.startswith("---\n")


def has_related_field(content: str) -> bool:
    """Check if frontmatter already has a related field."""
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if match:
        return "related:" in match.group(1)
    return False


def has_description_field(content: str) -> bool:
    """Check if frontmatter already has a description field."""
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if match:
        return "description:" in match.group(1)
    return False


def add_related_to_frontmatter(content: str, hub_link: str) -> str:
    """Add related field to existing frontmatter or create new frontmatter."""
    if has_related_field(content):
        return content  # Already has related

    if has_frontmatter(content):
        # Insert related before closing ---
        match = re.match(r"^(---\n)(.*?)(\n---)", content, re.DOTALL)
        if match:
            before = match.group(1)
            fm_body = match.group(2)
            after = match.group(3)
            rest = content[match.end():]
            return f"{before}{fm_body}\nrelated:\n  - \"{hub_link}\"{after}{rest}"
    else:
        # Create minimal frontmatter
        return f"---\nrelated:\n  - \"{hub_link}\"\n---\n{content}"

    return content


def main():
    apply = "--apply" in sys.argv

    graph = load_graph()
    orphans = graph.get("orphans", [])
    weakly_connected = graph.get("weakly_connected", [])

    # Combine: orphans + weakly_connected for maximum link density improvement
    targets = set(orphans + weakly_connected)

    print(f"Orphans: {len(orphans)}")
    print(f"Weakly connected: {len(weakly_connected)}")
    print(f"Total targets: {len(targets)}")
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print()

    connected = 0
    skipped = 0
    already_has = 0
    errors = 0

    for rel_path in sorted(targets):
        hub_link = get_hub_for_path(rel_path)
        if hub_link is None:
            skipped += 1
            continue

        file_path = VAULT_PATH / rel_path
        if not file_path.exists():
            errors += 1
            print(f"  MISSING: {rel_path}")
            continue

        content = file_path.read_text(encoding="utf-8")

        if has_related_field(content):
            already_has += 1
            continue

        new_content = add_related_to_frontmatter(content, hub_link)

        if new_content != content:
            tag = "ORPHAN" if rel_path in orphans else "WEAK"
            print(f"  [{tag}] {rel_path} → {hub_link}")
            connected += 1
            if apply:
                file_path.write_text(new_content, encoding="utf-8")

    print(f"\n{'='*50}")
    print(f"Connected: {connected}")
    print(f"Skipped (daily/template/internal): {skipped}")
    print(f"Already has related: {already_has}")
    print(f"Missing files: {errors}")
    if apply:
        print(f"Files modified: {connected}")


if __name__ == "__main__":
    main()
