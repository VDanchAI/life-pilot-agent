#!/usr/bin/env python3
"""
Link Builder for Obsidian Vault

Suggests and adds wiki-links based on content analysis.
Run with: uv run add_links.py [vault_path] [--dry-run]
"""

import re
import sys
from pathlib import Path
from collections import defaultdict


def extract_existing_links(content: str) -> set[str]:
    """Extract existing [[wiki-links]] from content."""
    pattern = r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]'
    return set(re.findall(pattern, content))


def find_mentions(content: str, note_titles: set[str]) -> list[tuple[str, int]]:
    """Find mentions of note titles in content without existing links."""
    existing = extract_existing_links(content)
    mentions = []

    for title in note_titles:
        if title in existing:
            continue
        if len(title) < 3:  # Skip very short titles
            continue

        # Case-insensitive search for title
        pattern = rf'\b{re.escape(title)}\b'
        for match in re.finditer(pattern, content, re.IGNORECASE):
            mentions.append((title, match.start()))

    return mentions


def suggest_moc_links(note_path: Path, moc_mapping: dict[str, str]) -> list[str]:
    """Suggest MOC links based on domain/tags."""
    suggestions = []
    domain = note_path.parts[0] if len(note_path.parts) > 1 else None

    if domain and domain in moc_mapping:
        suggestions.append(moc_mapping[domain])

    return suggestions


def build_moc_mapping(vault_path: Path) -> dict[str, str]:
    """Build mapping from domains to their MOC files."""
    mapping = {}
    moc_dir = vault_path / "MOC"

    if moc_dir.exists():
        for moc_file in moc_dir.glob("*.md"):
            moc_name = moc_file.stem
            # Map common domain patterns
            domain_patterns = {
                "ideas": "thoughts",
                "learnings": "thoughts",
                "reflections": "thoughts",
                "projects": "projects",
                "goals": "goals",
            }
            for pattern, domain in domain_patterns.items():
                if pattern.lower() in moc_name.lower():
                    mapping[domain] = moc_name

    return mapping


def analyze_and_suggest(vault_path: Path) -> dict:
    """Analyze vault and suggest new links."""
    suggestions: dict[str, list[dict]] = defaultdict(list)

    # Collect all note titles
    md_files = list(vault_path.rglob("*.md"))
    md_files = [
        f for f in md_files
        if not any(part.startswith('.') for part in f.relative_to(vault_path).parts)
    ]

    note_titles = {f.stem for f in md_files}
    moc_mapping = build_moc_mapping(vault_path)

    for md_file in md_files:
        rel_path = md_file.relative_to(vault_path)
        title = md_file.stem
        content = md_file.read_text(encoding="utf-8", errors="ignore")

        # Find unlinked mentions
        mentions = find_mentions(content, note_titles - {title})
        for mentioned_title, position in mentions:
            suggestions[title].append({
                "type": "mention",
                "target": mentioned_title,
                "position": position,
                "reason": f"'{mentioned_title}' mentioned but not linked",
            })

        # Suggest MOC links for orphan notes
        existing_links = extract_existing_links(content)
        moc_suggestions = suggest_moc_links(rel_path, moc_mapping)
        for moc in moc_suggestions:
            if moc not in existing_links:
                suggestions[title].append({
                    "type": "moc",
                    "target": moc,
                    "reason": f"Should link to [[{moc}]] MOC",
                })

    return dict(suggestions)


def apply_link(file_path: Path, target: str, dry_run: bool = True) -> bool:
    """Add a link to a note's related section."""
    content = file_path.read_text(encoding="utf-8")

    # Check if link already exists
    if f"[[{target}]]" in content:
        return False

    # Find or create "Related" section
    related_pattern = r'^## Related\s*$'
    match = re.search(related_pattern, content, re.MULTILINE)

    if match:
        # Add to existing Related section
        insert_pos = match.end()
        new_content = content[:insert_pos] + f"\n- [[{target}]]" + content[insert_pos:]
    else:
        # Add Related section at end
        new_content = content.rstrip() + f"\n\n## Related\n\n- [[{target}]]\n"

    if dry_run:
        print(f"[DRY RUN] Would add [[{target}]] to {file_path.name}")
        return True

    file_path.write_text(new_content, encoding="utf-8")
    print(f"Added [[{target}]] to {file_path.name}")
    return True


def format_suggestions(suggestions: dict) -> str:
    """Format suggestions as readable report."""
    if not suggestions:
        return "No link suggestions found. Vault is well-connected!"

    lines = [
        "# Link Suggestions",
        "",
        f"Found suggestions for {len(suggestions)} notes:",
        "",
    ]

    for note, items in sorted(suggestions.items()):
        lines.append(f"## [[{note}]]")
        for item in items:
            lines.append(f"- {item['type'].upper()}: Link to [[{item['target']}]]")
            lines.append(f"  - Reason: {item['reason']}")
        lines.append("")

    return "\n".join(lines)


def format_html(suggestions: dict) -> str:
    """Format suggestions as Telegram HTML."""
    if not suggestions:
        return "✅ <b>No link suggestions</b>\n\nVault is well-connected!"

    total = sum(len(v) for v in suggestions.values())

    lines = [
        f"🔗 <b>Link Suggestions</b>",
        "",
        f"<b>Found:</b> {total} suggestions for {len(suggestions)} notes",
        "",
    ]

    # Show top 10 suggestions
    count = 0
    for note, items in sorted(suggestions.items(), key=lambda x: -len(x[1])):
        if count >= 10:
            remaining = total - count
            lines.append(f"\n<i>... and {remaining} more suggestions</i>")
            break
        for item in items:
            lines.append(f"• [[{note}]] → [[{item['target']}]]")
            count += 1
            if count >= 10:
                break

    return "\n".join(lines)


def main():
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    apply_mode = "--apply" in sys.argv

    # Get vault path
    vault_path = None
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            vault_path = Path(arg)
            break

    if vault_path is None:
        # Default: assume script is in vault/.claude/skills/graph-builder/scripts/
        vault_path = Path(__file__).parent.parent.parent.parent.parent

    if not vault_path.exists():
        print(f"Error: Vault path not found: {vault_path}", file=sys.stderr)
        sys.exit(1)

    suggestions = analyze_and_suggest(vault_path)

    if apply_mode:
        # Apply all suggestions
        applied = 0
        for note, items in suggestions.items():
            note_path = vault_path / f"{note}.md"
            # Try to find the actual file
            matches = list(vault_path.rglob(f"{note}.md"))
            matches = [m for m in matches if not str(m).startswith('.')]

            if matches:
                note_path = matches[0]
                for item in items:
                    if apply_link(note_path, item["target"], dry_run):
                        applied += 1

        print(f"\n{'[DRY RUN] Would apply' if dry_run else 'Applied'} {applied} links")
    else:
        # Just report
        if "--html" in sys.argv:
            print(format_html(suggestions))
        elif "--json" in sys.argv:
            import json
            print(json.dumps(suggestions, indent=2))
        else:
            print(format_suggestions(suggestions))


if __name__ == "__main__":
    main()
