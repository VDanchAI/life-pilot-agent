#!/usr/bin/env python3
"""
Graph Analyzer for Obsidian Vault

Analyzes wiki-link structure and generates statistics.
Run with: uv run analyze.py [vault_path]
"""

import re
import sys
from collections import defaultdict
from pathlib import Path


def extract_links(content: str) -> list[str]:
    """Extract [[wiki-links]] from content."""
    pattern = r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]'
    return re.findall(pattern, content)


def get_note_title(path: Path) -> str:
    """Get note title from filename."""
    return path.stem


def analyze_vault(vault_path: Path) -> dict:
    """Analyze vault link structure."""
    notes: dict[str, dict] = {}
    links_from: dict[str, set] = defaultdict(set)  # note -> set of linked notes
    links_to: dict[str, set] = defaultdict(set)    # note -> set of notes linking to it

    # Collect all markdown files
    md_files = list(vault_path.rglob("*.md"))

    # Skip hidden directories and .claude
    md_files = [
        f for f in md_files
        if not any(part.startswith('.') for part in f.relative_to(vault_path).parts)
    ]

    # Build note index
    for md_file in md_files:
        rel_path = md_file.relative_to(vault_path)
        title = get_note_title(md_file)
        domain = str(rel_path.parts[0]) if len(rel_path.parts) > 1 else "root"

        notes[title] = {
            "path": str(rel_path),
            "domain": domain,
            "size": md_file.stat().st_size,
        }

    # Analyze links
    for md_file in md_files:
        title = get_note_title(md_file)
        content = md_file.read_text(encoding="utf-8", errors="ignore")

        for link in extract_links(content):
            # Handle links with paths like [[folder/note]]
            link_title = link.split("/")[-1] if "/" in link else link

            links_from[title].add(link_title)
            links_to[link_title].add(title)

    # Calculate statistics
    orphans = []
    for title, info in notes.items():
        incoming = len(links_to.get(title, set()))
        outgoing = len(links_from.get(title, set()))
        info["incoming"] = incoming
        info["outgoing"] = outgoing
        info["total_links"] = incoming + outgoing

        # Orphan: no incoming AND no outgoing links
        # Exclude MOC and root-level files from orphan detection
        if incoming == 0 and outgoing == 0:
            if info["domain"] not in ("MOC", "root"):
                orphans.append(title)

    # Domain statistics
    domain_stats: dict[str, dict] = defaultdict(lambda: {"count": 0, "links": 0})
    for title, info in notes.items():
        domain = info["domain"]
        domain_stats[domain]["count"] += 1
        domain_stats[domain]["links"] += info["total_links"]

    for domain in domain_stats:
        count = domain_stats[domain]["count"]
        if count > 0:
            domain_stats[domain]["avg_links"] = domain_stats[domain]["links"] / count

    # Most connected notes
    most_connected = sorted(
        notes.items(),
        key=lambda x: x[1]["total_links"],
        reverse=True
    )[:10]

    return {
        "total_notes": len(notes),
        "total_links": sum(len(v) for v in links_from.values()),
        "orphans": orphans,
        "orphan_count": len(orphans),
        "domain_stats": dict(domain_stats),
        "most_connected": [(t, n["total_links"]) for t, n in most_connected],
        "notes": notes,
        "links_from": {k: list(v) for k, v in links_from.items()},
        "links_to": {k: list(v) for k, v in links_to.items()},
    }


def format_report(stats: dict) -> str:
    """Format analysis as readable report."""
    lines = [
        "# Vault Graph Analysis",
        "",
        "## Overview",
        "",
        f"- **Total notes:** {stats['total_notes']}",
        f"- **Total links:** {stats['total_links']}",
        f"- **Orphan notes:** {stats['orphan_count']}",
        "",
    ]

    # Most connected
    if stats["most_connected"]:
        lines.append("## Most Connected Notes")
        lines.append("")
        for title, count in stats["most_connected"][:5]:
            lines.append(f"- [[{title}]] ({count} links)")
        lines.append("")

    # Domain stats
    lines.append("## Domain Statistics")
    lines.append("")
    lines.append("| Domain | Notes | Avg Links |")
    lines.append("|--------|-------|-----------|")
    for domain, data in sorted(stats["domain_stats"].items()):
        avg = data.get("avg_links", 0)
        lines.append(f"| {domain}/ | {data['count']} | {avg:.1f} |")
    lines.append("")

    # Orphans
    if stats["orphans"]:
        lines.append("## Orphan Notes (need links)")
        lines.append("")
        for title in stats["orphans"][:20]:
            note = stats["notes"][title]
            lines.append(f"- [[{title}]] ({note['domain']}/)")
        if len(stats["orphans"]) > 20:
            lines.append(f"- ... and {len(stats['orphans']) - 20} more")
        lines.append("")

    return "\n".join(lines)


def format_html(stats: dict) -> str:
    """Format analysis as Telegram HTML."""
    orphan_count = stats["orphan_count"]
    orphan_emoji = "⚠️" if orphan_count > 10 else "✅"

    lines = [
        f"📊 <b>Vault Graph Analysis</b>",
        "",
        f"<b>📝 Total notes:</b> {stats['total_notes']}",
        f"<b>🔗 Total links:</b> {stats['total_links']}",
        f"<b>{orphan_emoji} Orphan notes:</b> {orphan_count}",
        "",
    ]

    # Most connected
    if stats["most_connected"]:
        lines.append("<b>🏆 Most connected:</b>")
        for title, count in stats["most_connected"][:3]:
            lines.append(f"• [[{title}]] ({count})")
        lines.append("")

    # Weakest domain
    weakest = min(
        stats["domain_stats"].items(),
        key=lambda x: x[1].get("avg_links", 0)
    )
    lines.append(f"<b>⚡ Weakest domain:</b> {weakest[0]}/ (avg {weakest[1].get('avg_links', 0):.1f} links)")

    # Orphan preview
    if stats["orphans"]:
        lines.append("")
        lines.append("<b>📋 Sample orphans:</b>")
        for title in stats["orphans"][:5]:
            lines.append(f"• {title}")

    return "\n".join(lines)


def main():
    if len(sys.argv) > 1:
        vault_path = Path(sys.argv[1])
    else:
        # Default: assume script is in vault/.claude/skills/graph-builder/scripts/
        vault_path = Path(__file__).parent.parent.parent.parent.parent

    if not vault_path.exists():
        print(f"Error: Vault path not found: {vault_path}", file=sys.stderr)
        sys.exit(1)

    stats = analyze_vault(vault_path)

    # Output format based on args
    if "--html" in sys.argv:
        print(format_html(stats))
    elif "--json" in sys.argv:
        import json
        print(json.dumps(stats, indent=2))
    else:
        print(format_report(stats))


if __name__ == "__main__":
    main()
