#!/usr/bin/env python3
"""
Fix broken wiki-links in vault using pattern matching and heuristics.

Patterns handled:
1. Trailing backslash: [[business/crm/acme-corp]] with trailing backslash → clean
2. Wrong prefix: [[crm/projects/X]] → [[projects/clients/X]] or [[projects/leads/X]]
3. Stem match: [[acme-corp]] → [[business/crm/acme-corp]] (when unique match exists)
4. CRM sub-project → parent: [[business/crm/client-a-smm]] → [[business/crm/client-a]]
5. business/projects/ → parent CRM: [[business/projects/brand-x-campaign-2026]] → [[business/crm/brand-x]]
6. Plaintext company names (self-refs): [[Acme]] inside acme.md → remove wikilink
7. Goals aliases: [[3-weekly-2026-W05]] → remove
8. Internal paths (.claude/, vault/, scripts/): [[.claude/CLAUDE]] → `code ref`
9. Stub/concept links: [[craftsmanship]], [[ai-philosophy]] → plain text
10. Misc: attachments, meals.md, etc. → remove wikilink

Usage:
  uv run vault/.claude/skills/vault-health/scripts/fix_links.py          # dry-run
  uv run vault/.claude/skills/vault-health/scripts/fix_links.py --apply  # apply fixes
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict

SCRIPT_DIR = Path(__file__).parent
VAULT_PATH = SCRIPT_DIR.parents[3]
GRAPH_PATH = VAULT_PATH / ".graph" / "vault-graph.json"

IGNORE_DIRS = {".obsidian", "attachments", ".git", ".graph", ".claude", ".trash"}
EXCLUDE_PATTERNS = {"backup", ".backup", "business.backup"}

# Pattern A: CRM sub-project → parent CRM file
CRM_PARENT_MAP = {
    "client-a-smm": "client-a",
    "brand-x-meals-ncp": "brand-x",
    "brand-x-smm-region": "brand-x",
    "client-b-smm": "client-b",
    "client-c-wh": "client-c",
    "client-d-smm": "client-d",
    "client-e-influencers": "client-e",
    "techco-region": "techco",
    "brand-x-sub-smm": "brand-x",
    "brand-x-snacks-2026": "brand-x",
    "techco-eats-city": None,  # no parent — remove link
    "techco-eats-tc": None,  # no parent — remove link
    "brand-y": "brand-y-campaign",
}

# Pattern B: business/projects/ → parent CRM
PROJECT_CLIENT_MAP = {
    "brand-x-meals-ncp-2026": "brand-x",
    "client-a-smm-strategy-2026": "client-a",
    "client-a-smm": "client-a",
    "client-c-wellness": "client-c",
    "client-f-budget-2026": "client-f",
    "automaker-a-strategy-2026": "automaker-a",
    "client-d-smm-tender": "client-d",
    "automaker-b-bot-smm": "automaker-b",
    "client-b-baby-2026": "client-b",
    "brand-x-snacks-2026": "brand-x",
    "fmcg-co-region-rfi": "fmcg-co",
    "automaker-c-smm-tender": "automaker-c",
    "tobacco-co-hr-brand": "tobacco-co",
    "retailer-a-comstrat": "retailer-a",
}

# Pattern F: Stub/concept links that won't become files → remove wikilink
STUB_LINKS = {
    "craftsmanship", "ai-philosophy", "quality", "second-brain", "telegram-bot",
    "note", "title", "frontend-design", "accessibility", "vault-processor",
    "wikilinks", "sample-stub-link",
}

# Direct replacements for known mismatches
DIRECT_REPLACE_MAP = {
    "business/network/partner-alias": "business/network/partner-full-name",
    "thoughts/ideas/sample-algorithm": "thoughts/ideas/2026-02-05-sample-agent-algorithm",
}

# Pattern F extended: Long sentence-links from external sources
SENTENCE_LINK_PREFIXES = [
    "LLM attention degrades",
    "fresh context per task",
    "note titles should function",
    "Agent Memory System",
    "AI agents need layered memory",
]


def load_graph():
    """Load vault-graph.json."""
    if not GRAPH_PATH.exists():
        print("Error: vault-graph.json not found. Run analyze.py first.")
        sys.exit(1)
    return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))


def build_stem_index():
    """Build index: stem → [full_paths]."""
    index = defaultdict(list)
    md_files = [
        f for f in VAULT_PATH.rglob("*.md")
        if not any(d in f.parts for d in IGNORE_DIRS)
        and not any(p in str(f) for p in EXCLUDE_PATTERNS)
    ]
    for f in md_files:
        rel = str(f.relative_to(VAULT_PATH))
        stem = f.stem
        index[stem].append(rel)
        # Also index by path without .md
        index[rel.removesuffix(".md")].append(rel)
    return index


def find_crm_file(client_name: str) -> str | None:
    """Find CRM file for a client name in business/crm/."""
    for prefix in ["business/crm/"]:
        candidate = VAULT_PATH / f"{prefix}{client_name}.md"
        if candidate.exists():
            return f"{prefix}{client_name}"
    return None


def suggest_fix(broken_from: str, broken_to: str, stem_index: dict) -> tuple[str | None, str]:
    """Suggest a fix for a broken link target.

    Returns (suggestion, action) where action is:
    - 'replace': replace the wikilink target
    - 'remove': remove the wikilink, keep display text
    - 'none': no fix found
    """
    target = broken_to

    # Direct replacement map (known mismatches)
    if target in DIRECT_REPLACE_MAP:
        replacement = DIRECT_REPLACE_MAP[target]
        # Verify the target file exists
        if (VAULT_PATH / f"{replacement}.md").exists():
            return replacement, "replace"

    # Pattern 1: Trailing backslash
    if target.endswith("\\"):
        clean = target.rstrip("\\")
        if clean in stem_index:
            return clean, "replace"
        if clean + ".md" in stem_index:
            return clean, "replace"
        stem = Path(clean).stem
        if stem in stem_index and len(stem_index[stem]) == 1:
            return stem_index[stem][0].removesuffix(".md"), "replace"

    # Pattern 2: Wrong prefix (crm/projects/X → projects/clients/X or projects/leads/X)
    if target.startswith("crm/projects/"):
        name = target.removeprefix("crm/projects/").rstrip("\\")
        for prefix in ["projects/clients/", "projects/leads/"]:
            candidate = prefix + name
            if candidate in stem_index or candidate + ".md" in stem_index:
                return candidate, "replace"

    # Pattern A: CRM sub-project → parent
    for crm_prefix in ["business/crm/"]:
        if target.startswith(crm_prefix):
            sub_name = target.removeprefix(crm_prefix)
            if sub_name in CRM_PARENT_MAP:
                parent = CRM_PARENT_MAP[sub_name]
                if parent is None:
                    return None, "remove"
                parent_path = find_crm_file(parent)
                if parent_path:
                    return parent_path, "replace"

    # Pattern B: business/projects/ → parent CRM
    if target.startswith("business/projects/"):
        project_name = target.removeprefix("business/projects/")
        if project_name in PROJECT_CLIENT_MAP:
            client = PROJECT_CLIENT_MAP[project_name]
            parent_path = find_crm_file(client)
            if parent_path:
                return parent_path, "replace"

    # Pattern C: Plaintext company names (self-references inside CRM files)
    # e.g. business/crm/acme-corp.md has [[Acme Corp]] — remove the wikilink
    if not "/" in target and target[0:1].isupper() and broken_from.startswith(("business/crm/", "projects/crm/")):
        return None, "remove"

    # Pattern D: Goals aliases (3-weekly-2026-W05 etc.)
    if re.match(r"3-weekly-2026-W\d+", target):
        return None, "remove"

    # Pattern E: Internal paths (.claude/, vault/, scripts/, ~/)
    if any(target.startswith(p) for p in [".claude/", "vault/", "scripts/", "../", "~/"]):
        return None, "remove"

    # Pattern F: Stub/concept links
    if target in STUB_LINKS:
        return None, "remove"

    # Pattern F extended: Sentence-links from external sources
    for prefix in SENTENCE_LINK_PREFIXES:
        if target.startswith(prefix):
            return None, "remove"

    # Pattern G: Known unmatchable files → remove
    known_removable = {
        "contacts/partner-org.json", "meals.md", "brand-x-tasks-handoff.md",
        "thoughts/reflections/2026-01-03-data-backup",
        "2026-01-05-project-ssr-migration",
    }
    if target in known_removable:
        return None, "remove"

    # Attachments → remove wikilink (they're embeds, not graph nodes)
    if target.startswith("attachments/"):
        return None, "remove"

    # thoughts/ references that don't exist → check if stem exists
    if target.startswith("thoughts/"):
        stem = Path(target).stem
        if stem in stem_index and len(stem_index[stem]) == 1:
            return stem_index[stem][0].removesuffix(".md"), "replace"

    # Pattern 3: Stem-only match (e.g. "acme-corp" → "business/crm/acme-corp")
    stem = Path(target.rstrip("\\")).stem
    if stem in stem_index:
        matches = stem_index[stem]
        if len(matches) == 1:
            return matches[0].removesuffix(".md"), "replace"

    # Projects paths that might resolve differently
    if target.startswith("projects/"):
        stem = Path(target).stem
        if stem in stem_index and len(stem_index[stem]) == 1:
            return stem_index[stem][0].removesuffix(".md"), "replace"

    # business/network/ that doesn't exist
    if target.startswith("business/network/"):
        stem = Path(target).stem
        if stem in stem_index and len(stem_index[stem]) == 1:
            return stem_index[stem][0].removesuffix(".md"), "replace"

    # Final fallback: if the link has a path (contains /) and target doesn't exist → remove
    # This catches remaining broken paths like projects/leads/contact-name, etc.
    if "/" in target:
        target_path = VAULT_PATH / f"{target}.md"
        if not target_path.exists():
            return None, "remove"

    return None, "none"


def apply_replace(file_path: Path, old_link: str, new_link: str) -> bool:
    """Replace broken link target in file."""
    content = file_path.read_text(encoding="utf-8")

    # Match [[old_link]], [[old_link|alias]], [[old_link#section]], [[old_link\|alias]] (table-escaped)
    escaped = re.escape(old_link)
    pattern = rf"\[\[{escaped}(\\?[|\]#])"
    replacement = f"[[{new_link}\\1"

    new_content = re.sub(pattern, replacement, content)

    if new_content != content:
        file_path.write_text(new_content, encoding="utf-8")
        return True
    return False


def apply_remove(file_path: Path, old_link: str) -> bool:
    """Remove wikilink, keeping display text or link target as plain text."""
    content = file_path.read_text(encoding="utf-8")

    escaped = re.escape(old_link)

    # [[old_link|Display Text]] → Display Text
    pattern_with_alias = rf"\[\[{escaped}\|([^\]]+)\]\]"
    new_content = re.sub(pattern_with_alias, r"\1", content)

    if new_content != content:
        file_path.write_text(new_content, encoding="utf-8")
        return True

    # [[old_link]] → old_link (just the text)
    # For paths, use just the stem; for names, use as-is
    if "/" in old_link:
        display = Path(old_link).stem.replace("-", " ").title()
    else:
        display = old_link

    pattern_plain = rf"\[\[{escaped}\]\]"
    new_content = re.sub(pattern_plain, display, content)

    if new_content != content:
        file_path.write_text(new_content, encoding="utf-8")
        return True

    return False


def main():
    apply = "--apply" in sys.argv

    graph = load_graph()
    broken_links = graph.get("broken_links", [])
    stem_index = build_stem_index()

    print(f"Broken links: {len(broken_links)}")
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print()

    # Group by source file
    by_source = defaultdict(list)
    for bl in broken_links:
        by_source[bl["from"]].append(bl["to"])

    replacements = []
    removals = []
    unfixable = []

    for source, targets in sorted(by_source.items()):
        for target in targets:
            suggestion, action = suggest_fix(source, target, stem_index)
            if action == "replace" and suggestion:
                replacements.append((source, target, suggestion))
            elif action == "remove":
                removals.append((source, target))
            else:
                unfixable.append((source, target))

    # Deduplicate
    seen = set()
    unique_replacements = []
    for src, old, new in replacements:
        key = (src, old, new)
        if key not in seen:
            seen.add(key)
            unique_replacements.append((src, old, new))
    replacements = unique_replacements

    seen_removals = set()
    unique_removals = []
    for src, old in removals:
        key = (src, old)
        if key not in seen_removals:
            seen_removals.add(key)
            unique_removals.append((src, old))
    removals = unique_removals

    print(f"Replacements: {len(replacements)}")
    print(f"Removals: {len(removals)}")
    print(f"Unfixable: {len(unfixable)}")
    print()

    if replacements:
        print("=== REPLACEMENTS ===")
        applied = 0
        for src, old, new in replacements:
            print(f"  {src}: [[{old}]] → [[{new}]]")
            if apply:
                src_path = VAULT_PATH / src
                if src_path.exists() and apply_replace(src_path, old, new):
                    applied += 1
        if apply:
            print(f"\nApplied: {applied}/{len(replacements)} replacements")

    if removals:
        print("\n=== REMOVALS (wikilink → plain text) ===")
        removed = 0
        for src, old in removals:
            print(f"  {src}: [[{old}]] → plain text")
            if apply:
                src_path = VAULT_PATH / src
                if src_path.exists() and apply_remove(src_path, old):
                    removed += 1
        if apply:
            print(f"\nRemoved: {removed}/{len(removals)} wikilinks")

    if unfixable:
        print("\n=== UNFIXABLE (manual review needed) ===")
        for src, target in unfixable:
            print(f"  {src} → {target}")

    # Summary
    total_fixed = len(replacements) + len(removals)
    print(f"\n{'='*50}")
    print(f"Total fixable: {total_fixed}/{len(broken_links)}")
    print(f"Unfixable: {len(unfixable)}")


if __name__ == "__main__":
    main()
