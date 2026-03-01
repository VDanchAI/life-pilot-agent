#!/usr/bin/env python3
"""
memory-engine.py — Universal memory management for AI agents.

Implements Ebbinghaus-inspired forgetting curve with tiered recall.
Works with any directory of markdown files.

Commands:
  scan    [dir]           Analyze files, report stats (no changes)
  init    [dir]           Add YAML frontmatter to files missing it
  decay   [dir]           Update relevance scores and tiers
  touch   <file>          Reset file to active (on read/use)
  creative <N> [dir]      Random N cards from cold/archive tiers
  stats   [dir]           Show tier distribution and health metrics

Options:
  --config <path>         Config JSON (default: .memory-config.json in target dir)
  --dry-run               Preview changes without writing
  --verbose               Show per-file details

Config (.memory-config.json):
{
  "tiers": {
    "active": 7,          // days threshold
    "warm": 21,
    "cold": 60
    // beyond cold = archive
  },
  "decay_rate": 0.015,    // relevance loss per day (linear)
  "relevance_floor": 0.1, // minimum relevance
  "skip_patterns": ["_index.md", "MOC-*"],
  "type_inference": {
    "crm/": "crm",
    "leads/": "lead",
    "personal/": "personal"
  },
  "use_git_dates": true
}
"""

import os
import re
import sys
import json
import random
import subprocess
from datetime import datetime, date
from pathlib import Path
from typing import Optional

# ─── defaults ───────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "tiers": {"active": 7, "warm": 21, "cold": 60},
    "decay_rate": 0.015,
    "relevance_floor": 0.1,
    "skip_patterns": ["_index.md"],
    "type_inference": {},
    "use_git_dates": True,
}

TODAY = date.today()

# ─── YAML frontmatter parsing ──────────────────────────────────

def parse_frontmatter(content: str) -> tuple[dict, str, bool]:
    """Parse YAML frontmatter. Returns (fields, body, had_yaml)."""
    if content.startswith("---\n"):
        end = content.find("\n---\n", 4)
        if end != -1:
            yaml_block = content[4:end]
            body = content[end + 5:]
            fields = {}
            for line in yaml_block.split("\n"):
                if ":" in line:
                    key, _, val = line.partition(":")
                    fields[key.strip()] = val.strip()
            return fields, body, True
    return {}, content, False


def build_frontmatter(fields: dict, field_order: list[str] | None = None) -> str:
    """Build YAML frontmatter from dict, preserving field order."""
    if field_order is None:
        field_order = [
            "type", "title", "description", "tags",
            "industry", "source", "priority", "status", "region",
            "owner", "responsible", "domain", "related", "client",
            "deal_status", "deal_deadline", "deadline",
            "created", "updated", "last_accessed", "relevance", "tier",
        ]
    lines = []
    used = set()
    for key in field_order:
        if key in fields:
            lines.append(f"{key}: {fields[key]}")
            used.add(key)
    for key, val in fields.items():
        if key not in used:
            lines.append(f"{key}: {val}")
    return "---\n" + "\n".join(lines) + "\n---\n"


# ─── date resolution ───────────────────────────────────────────

def get_git_date(filepath: Path) -> date | None:
    """Last git commit date for file."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", str(filepath)],
            capture_output=True, text=True,
            cwd=filepath.parent, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return date.fromisoformat(result.stdout.strip()[:10])
    except Exception:
        pass
    return None


def get_best_date(fields: dict, filepath: Path, use_git: bool = True) -> date:
    """Most recent date from YAML fields, git history, or file mtime."""
    candidates = []
    for field in ["last_accessed", "updated", "created"]:
        val = fields.get(field, "")
        try:
            candidates.append(date.fromisoformat(val[:10]))
        except (ValueError, IndexError):
            continue
    if use_git:
        git_date = get_git_date(filepath)
        if git_date:
            candidates.append(git_date)
    if not candidates:
        mtime = os.path.getmtime(filepath)
        candidates.append(date.fromtimestamp(mtime))
    return max(candidates)


# ─── core logic ─────────────────────────────────────────────────

def calc_relevance(days: int, rate: float, floor: float) -> float:
    """Linear decay with floor."""
    return round(max(floor, 1.0 - days * rate), 2)


def calc_tier(days: int, tiers: dict, current_tier: str = "") -> str:
    """Assign tier based on days since last access."""
    if current_tier == "core":
        return "core"  # never auto-demote core
    sorted_tiers = sorted(tiers.items(), key=lambda x: x[1])
    for tier_name, threshold in sorted_tiers:
        if days <= threshold:
            return tier_name
    return "archive"


def infer_type(filepath: Path, type_map: dict) -> str:
    """Infer card type from path using configurable mapping."""
    path_str = str(filepath)
    for pattern, card_type in type_map.items():
        if pattern in path_str:
            return card_type
    return "note"


def should_skip(filepath: Path, patterns: list[str]) -> bool:
    """Check if file matches skip patterns."""
    import fnmatch
    name = filepath.name
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def infer_title(body: str) -> str:
    """Extract title from first H1 heading."""
    for line in body.split("\n")[:10]:
        if line.startswith("# "):
            return line[2:].strip()
    return ""


# ─── config ─────────────────────────────────────────────────────

def load_config(target_dir: Path, config_path: str | None = None) -> dict:
    """Load config from file or return defaults."""
    if config_path:
        p = Path(config_path)
    else:
        p = target_dir / ".memory-config.json"
    if p.exists():
        with open(p) as f:
            user = json.load(f)
        # Merge with defaults
        config = {**DEFAULT_CONFIG, **user}
        config["tiers"] = {**DEFAULT_CONFIG["tiers"], **user.get("tiers", {})}
        return config
    return DEFAULT_CONFIG.copy()


def save_default_config(target_dir: Path):
    """Write default config file."""
    p = target_dir / ".memory-config.json"
    with open(p, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    print(f"  wrote default config: {p}")


# ─── commands ───────────────────────────────────────────────────

def find_cards(target_dir: Path, config: dict) -> list[Path]:
    """Find all markdown files, respecting skip patterns."""
    cards = sorted(target_dir.rglob("*.md"))
    return [c for c in cards if c.exists() and not c.is_symlink() and not should_skip(c, config["skip_patterns"])]


def cmd_scan(target_dir: Path, config: dict, verbose: bool = False):
    """Analyze files without changes."""
    cards = find_cards(target_dir, config)
    with_yaml = 0
    without_yaml = 0
    has_relevance = 0
    has_tier = 0
    total_bytes = 0

    for card in cards:
        content = card.read_text(encoding="utf-8", errors="replace")
        total_bytes += len(content.encode("utf-8"))
        fields, body, had_yaml = parse_frontmatter(content)
        if had_yaml:
            with_yaml += 1
        else:
            without_yaml += 1
        if "relevance" in fields:
            has_relevance += 1
        if "tier" in fields:
            has_tier += 1
        if verbose and not had_yaml:
            print(f"  no yaml: {card.relative_to(target_dir)}")

    print(f"\n  scan results for {target_dir}:")
    print(f"    total files:     {len(cards)}")
    print(f"    with yaml:       {with_yaml}")
    print(f"    without yaml:    {without_yaml}")
    print(f"    has relevance:   {has_relevance}")
    print(f"    has tier:        {has_tier}")
    print(f"    total size:      {total_bytes / 1024:.0f} KB")
    print(f"    avg file size:   {total_bytes / max(len(cards), 1) / 1024:.1f} KB")

    if without_yaml:
        print(f"\n  → run 'init' to add YAML frontmatter to {without_yaml} files")
    if not has_relevance:
        print(f"  → run 'decay' to add relevance scores and tiers")


def cmd_init(target_dir: Path, config: dict, dry_run: bool = False, verbose: bool = False):
    """Add YAML frontmatter to files missing it."""
    cards = find_cards(target_dir, config)
    added = 0

    for card in cards:
        content = card.read_text(encoding="utf-8", errors="replace")
        fields, body, had_yaml = parse_frontmatter(content)
        if had_yaml:
            continue

        # Create minimal frontmatter
        new_fields = {
            "type": infer_type(card, config["type_inference"]),
        }
        title = infer_title(body)
        if title:
            new_fields["title"] = title

        ref_date = get_best_date({}, card, config["use_git_dates"])
        new_fields["last_accessed"] = ref_date.isoformat()
        days = max(0, (TODAY - ref_date).days)
        new_fields["relevance"] = str(calc_relevance(days, config["decay_rate"], config["relevance_floor"]))
        new_fields["tier"] = calc_tier(days, config["tiers"])

        new_content = build_frontmatter(new_fields) + body
        if not dry_run:
            card.write_text(new_content, encoding="utf-8")
        added += 1
        if verbose:
            print(f"  {'[dry] ' if dry_run else ''}init: {card.relative_to(target_dir)} → {new_fields['tier']}")

    print(f"\n  {'DRY RUN — ' if dry_run else ''}init results:")
    print(f"    files processed: {len(cards)}")
    print(f"    frontmatter added: {added}")


def cmd_decay(target_dir: Path, config: dict, dry_run: bool = False, verbose: bool = False):
    """Update relevance and tiers based on time decay."""
    cards = find_cards(target_dir, config)
    results = []

    for card in cards:
        content = card.read_text(encoding="utf-8", errors="replace")
        fields, body, had_yaml = parse_frontmatter(content)

        ref_date = get_best_date(fields, card, config["use_git_dates"])
        days = max(0, (TODAY - ref_date).days)

        old_tier = fields.get("tier", "")
        new_relevance = calc_relevance(days, config["decay_rate"], config["relevance_floor"])
        new_tier = calc_tier(days, config["tiers"], old_tier)

        if "last_accessed" not in fields:
            fields["last_accessed"] = ref_date.isoformat()
        if "type" not in fields:
            fields["type"] = infer_type(card, config["type_inference"])

        fields["relevance"] = str(new_relevance)
        fields["tier"] = new_tier

        new_content = build_frontmatter(fields) + body
        changed = new_content != content

        if changed and not dry_run:
            card.write_text(new_content, encoding="utf-8")

        results.append({
            "path": str(card.relative_to(target_dir)),
            "days": days,
            "relevance": new_relevance,
            "tier": new_tier,
            "changed": changed,
        })

        if verbose and changed:
            print(f"  {'[dry] ' if dry_run else ''}{card.relative_to(target_dir)}: {old_tier or '?'}→{new_tier} r={new_relevance}")

    # Stats
    tiers = {}
    changed_count = sum(1 for r in results if r["changed"])
    for r in results:
        tiers[r["tier"]] = tiers.get(r["tier"], 0) + 1
    avg_rel = sum(r["relevance"] for r in results) / max(len(results), 1)

    print(f"\n  {'DRY RUN — ' if dry_run else ''}decay results:")
    print(f"    total: {len(results)}, changed: {changed_count}")
    print(f"    avg relevance: {avg_rel:.2f}")
    for tier in ["core", "active", "warm", "cold", "archive"]:
        count = tiers.get(tier, 0)
        bar = "█" * (count // 3)
        if count:
            print(f"    {tier:8s}: {count:4d} {bar}")


def cmd_touch(filepath: str, config: dict):
    """Promote a file one tier up (graduated recall).

    archive → cold → warm → active → active (refresh)
    Each touch promotes one level, not straight to top.
    Natural spaced repetition: multiple reads = stronger memory.
    """
    p = Path(filepath)
    if not p.exists():
        print(f"  error: {filepath} not found")
        sys.exit(1)

    content = p.read_text(encoding="utf-8", errors="replace")
    fields, body, had_yaml = parse_frontmatter(content)

    if fields.get("tier") == "core":
        fields["last_accessed"] = TODAY.isoformat()
        fields["relevance"] = "1.0"
        new_content = build_frontmatter(fields) + body
        p.write_text(new_content, encoding="utf-8")
        print(f"  touched: {filepath} → core (refreshed)")
        return

    tiers_cfg = config["tiers"]
    # Promotion targets: set last_accessed to midpoint of next-higher tier
    # archive → cold: midpoint of cold range
    # cold → warm: midpoint of warm range
    # warm → active: midpoint of active range
    # active → active: today (refresh)
    cold_threshold = tiers_cfg.get("cold", 60)
    warm_threshold = tiers_cfg.get("warm", 21)
    active_threshold = tiers_cfg.get("active", 7)

    current_tier = fields.get("tier", "archive")
    if current_tier == "archive":
        # Promote to cold: set last_accessed to midpoint of cold range
        target_days = (warm_threshold + cold_threshold) // 2
        new_tier = "cold"
    elif current_tier == "cold":
        # Promote to warm: midpoint of warm range
        target_days = (active_threshold + warm_threshold) // 2
        new_tier = "warm"
    elif current_tier == "warm":
        # Promote to active: midpoint of active range
        target_days = active_threshold // 2
        new_tier = "active"
    else:
        # Already active: refresh to today
        target_days = 0
        new_tier = "active"

    from datetime import timedelta
    new_date = TODAY - timedelta(days=target_days)
    new_relevance = calc_relevance(target_days, config["decay_rate"], config["relevance_floor"])

    fields["last_accessed"] = new_date.isoformat()
    fields["relevance"] = str(new_relevance)
    fields["tier"] = new_tier

    new_content = build_frontmatter(fields) + body
    p.write_text(new_content, encoding="utf-8")
    print(f"  touched: {filepath} → {current_tier}→{new_tier}, relevance={new_relevance}")


def cmd_creative(n: int, target_dir: Path, config: dict):
    """Random sample from cold/archive tiers for divergent thinking."""
    cards = find_cards(target_dir, config)
    cold_cards = []

    for card in cards:
        content = card.read_text(encoding="utf-8", errors="replace")
        fields, body, had_yaml = parse_frontmatter(content)
        tier = fields.get("tier", "")
        if tier in ("cold", "archive", "warm"):
            title = fields.get("title", "") or infer_title(body)
            cold_cards.append({
                "path": str(card.relative_to(target_dir)),
                "tier": tier,
                "relevance": fields.get("relevance", "?"),
                "title": title,
                "last_accessed": fields.get("last_accessed", "?"),
            })

    if not cold_cards:
        print("  no cold/archive cards found — memory is too fresh")
        return

    sample = random.sample(cold_cards, min(n, len(cold_cards)))
    print(f"\n  🎲 creative recall — {len(sample)} random cards:")
    for card in sample:
        print(f"    [{card['tier']}] {card['title'] or card['path']}")
        print(f"           {card['path']} (r={card['relevance']}, last={card['last_accessed']})")
    print(f"\n  read these cards and look for unexpected connections to your current task")


def cmd_daily(target_dir: Path, config: dict, dry_run: bool = False, verbose: bool = False):
    """Bootstrap and decay daily files (YYYY-MM-DD.md pattern)."""
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
    daily_files = sorted(
        f for f in target_dir.rglob("*.md")
        if date_pattern.match(f.name)
    )

    if not daily_files:
        print(f"  no daily files (YYYY-MM-DD.md) found in {target_dir}")
        return

    results = []
    for f in daily_files:
        content = f.read_text(encoding="utf-8", errors="replace")
        fields, body, had_yaml = parse_frontmatter(content)

        # Extract date from filename
        file_date = date.fromisoformat(f.stem)
        days = max(0, (TODAY - file_date).days)

        # Use file_date as reference (not git/mtime — daily files are date-intrinsic)
        la = fields.get("last_accessed", "")
        try:
            last_acc = date.fromisoformat(la[:10])
            # Use most recent of: file_date, last_accessed
            ref_days = max(0, (TODAY - max(file_date, last_acc)).days)
        except (ValueError, IndexError):
            ref_days = days

        new_relevance = calc_relevance(ref_days, config["decay_rate"], config["relevance_floor"])
        old_tier = fields.get("tier", "")
        new_tier = calc_tier(ref_days, config["tiers"], old_tier)

        fields["type"] = "daily"
        fields["date"] = file_date.isoformat()
        if "last_accessed" not in fields:
            fields["last_accessed"] = file_date.isoformat()
        fields["relevance"] = str(new_relevance)
        fields["tier"] = new_tier

        new_content = build_frontmatter(fields) + body
        changed = new_content != content

        if changed and not dry_run:
            f.write_text(new_content, encoding="utf-8")

        results.append({
            "file": f.name,
            "date": file_date.isoformat(),
            "days": ref_days,
            "relevance": new_relevance,
            "tier": new_tier,
            "changed": changed,
        })

        if verbose:
            print(f"  {'[dry] ' if dry_run else ''}{f.name}: {old_tier or '?'}→{new_tier} r={new_relevance} ({ref_days}d)")

    # Summary
    tiers = {}
    for r in results:
        tiers[r["tier"]] = tiers.get(r["tier"], 0) + 1
    changed_count = sum(1 for r in results if r["changed"])

    print(f"\n  {'DRY RUN — ' if dry_run else ''}daily results:")
    print(f"    files: {len(results)}, changed: {changed_count}")
    for tier in ["active", "warm", "cold", "archive"]:
        count = tiers.get(tier, 0)
        if count:
            dates = [r["date"] for r in results if r["tier"] == tier]
            print(f"    {tier:8s}: {count:3d}  ({dates[0]}..{dates[-1]})")


def cmd_stats(target_dir: Path, config: dict):
    """Show comprehensive memory health stats."""
    cards = find_cards(target_dir, config)
    tiers = {}
    total_bytes = 0
    stale_count = 0
    no_yaml = 0

    for card in cards:
        content = card.read_text(encoding="utf-8", errors="replace")
        total_bytes += len(content.encode("utf-8"))
        fields, body, had_yaml = parse_frontmatter(content)
        if not had_yaml:
            no_yaml += 1
        tier = fields.get("tier", "unknown")
        tiers[tier] = tiers.get(tier, 0) + 1
        try:
            la = date.fromisoformat(fields.get("last_accessed", "")[:10])
            if (TODAY - la).days > 90:
                stale_count += 1
        except (ValueError, IndexError):
            pass

    print(f"\n  memory health — {target_dir}")
    print(f"  {'─' * 40}")
    print(f"  total cards:       {len(cards)}")
    print(f"  total size:        {total_bytes / 1024:.0f} KB")
    print(f"  without yaml:      {no_yaml}")
    print(f"  stale (>90 days):  {stale_count}")
    print(f"  {'─' * 40}")
    print(f"  tier distribution:")
    for tier in ["core", "active", "warm", "cold", "archive", "unknown"]:
        count = tiers.get(tier, 0)
        if count:
            pct = count / len(cards) * 100
            bar = "█" * int(pct / 2)
            print(f"    {tier:8s}: {count:4d} ({pct:4.1f}%) {bar}")

    # Context budget estimate (assuming ~4 chars per token)
    active_bytes = 0
    for card in cards:
        content = card.read_text(encoding="utf-8", errors="replace")
        fields, _, _ = parse_frontmatter(content)
        if fields.get("tier") in ("core", "active"):
            active_bytes += len(content.encode("utf-8"))
    print(f"  {'─' * 40}")
    print(f"  active context:    {active_bytes / 1024:.0f} KB (~{active_bytes // 4:,} tokens)")
    print(f"  total context:     {total_bytes / 1024:.0f} KB (~{total_bytes // 4:,} tokens)")


# ─── main ───────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    cmd = args[0]
    dry_run = "--dry-run" in args
    verbose = "--verbose" in args

    # Find config path
    config_path = None
    if "--config" in args:
        idx = args.index("--config")
        config_path = args[idx + 1] if idx + 1 < len(args) else None

    # Find target directory (first non-flag argument after command)
    target = None
    for a in args[1:]:
        if not a.startswith("-") and a != config_path:
            target = a
            break

    if cmd == "touch":
        if not target:
            print("  error: touch requires a file path")
            sys.exit(1)
        config = load_config(Path(target).parent, config_path)
        cmd_touch(target, config)
        return

    if cmd == "creative":
        n = 5
        creative_dir = None
        for a in args[1:]:
            if not a.startswith("-"):
                try:
                    n = int(a)
                except ValueError:
                    creative_dir = a
        target_dir = Path(creative_dir) if creative_dir else Path(".")
        config = load_config(target_dir, config_path)
        cmd_creative(n, target_dir, config)
        return

    target_dir = Path(target) if target else Path(".")
    if not target_dir.is_dir():
        print(f"  error: {target_dir} is not a directory")
        sys.exit(1)

    config = load_config(target_dir, config_path)

    if cmd == "scan":
        cmd_scan(target_dir, config, verbose)
    elif cmd == "init":
        cmd_init(target_dir, config, dry_run, verbose)
    elif cmd == "decay":
        cmd_decay(target_dir, config, dry_run, verbose)
    elif cmd == "daily":
        cmd_daily(target_dir, config, dry_run, verbose)
    elif cmd == "stats":
        cmd_stats(target_dir, config)
    elif cmd == "config":
        save_default_config(target_dir)
    else:
        print(f"  unknown command: {cmd}")
        print("  commands: scan, init, decay, daily, touch, creative, stats, config")
        sys.exit(1)


if __name__ == "__main__":
    main()
