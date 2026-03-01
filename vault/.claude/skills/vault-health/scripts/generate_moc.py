#!/usr/bin/env python3
"""
Generate explicit-wikilinks MOC files for Business and Projects.

Reads CRM/client/lead files, extracts frontmatter, groups by industry,
and generates MOC markdown with explicit wikilinks:
  - [[business/crm/acme-corp|Acme Corp]] — Active, High priority, POST-LAUNCH deal

Output:
  - vault/MOC/MOC-business.md — Business CRM Map of Content
  - vault/MOC/MOC-projects.md — Projects Map of Content

Usage:
  uv run vault/.claude/skills/graph-builder/scripts/generate_moc.py
"""

import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Paths
SCRIPT_DIR = Path(__file__).parent
VAULT_PATH = SCRIPT_DIR.parents[3]  # vault/.claude/skills/graph-builder/scripts -> vault
MOC_DIR = VAULT_PATH / "MOC"
BUSINESS_CRM_DIR = VAULT_PATH / "business" / "crm"
PROJECTS_DIR = VAULT_PATH / "projects"


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


def extract_title(content: str) -> str | None:
    """Extract first H1 heading from markdown content."""
    match = re.search(r"^# (.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def build_context_phrase(fm: dict[str, str]) -> str:
    """Build a context phrase from frontmatter fields.

    Pattern: status, priority, deal_status, region
    Example: "Active, High priority, POST-LAUNCH deal"
    """
    parts = []

    status = fm.get("status", "")
    if status:
        parts.append(status)

    priority = fm.get("priority", "")
    if priority:
        parts.append(f"{priority} priority")

    deal_status = fm.get("deal_status", "")
    if deal_status:
        parts.append(f"{deal_status} deal")

    region = fm.get("region", "")
    if region:
        parts.append(region)

    return ", ".join(parts)


def relative_path(file_path: Path) -> str:
    """Get vault-relative path without .md extension."""
    rel = file_path.relative_to(VAULT_PATH)
    return str(rel).removesuffix(".md")


def generate_business_moc() -> str:
    """Generate MOC-business.md content with explicit wikilinks grouped by industry."""

    # Collect all CRM files
    records: list[dict] = []
    for md_file in sorted(BUSINESS_CRM_DIR.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        title = extract_title(content) or md_file.stem.replace("-", " ").title()
        rel = relative_path(md_file)

        records.append({
            "path": rel,
            "title": title,
            "industry": fm.get("industry", "Unknown"),
            "status": fm.get("status", ""),
            "priority": fm.get("priority", ""),
            "deal_status": fm.get("deal_status", ""),
            "region": fm.get("region", ""),
            "updated": fm.get("updated", ""),
            "fm": fm,
        })

    # Group by industry
    by_industry: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        by_industry[rec["industry"]].append(rec)

    # Sort industries by count (descending), then alphabetically
    sorted_industries = sorted(
        by_industry.keys(),
        key=lambda ind: (-len(by_industry[ind]), ind),
    )

    # Count active deals and high priority
    active_deals = [r for r in records if r["deal_status"] and r["deal_status"] not in ("StandBy", "Отказано")]
    high_priority = [r for r in records if r["priority"] == "High"]

    now = datetime.now().strftime("%Y-%m-%d")

    lines = [
        "# MOC - Business",
        "",
        "> Map of Content for Business CRM data",
        f"> Generated: {now} | {len(records)} records, {len(active_deals)} active deals, {len(high_priority)} high priority",
        "",
        "[[business/_index|Business Data Overview]]",
        "",
        "---",
        "",
    ]

    # Active Deals section (explicit wikilinks)
    if active_deals:
        lines.append(f"## Active Deals ({len(active_deals)})")
        lines.append("")
        # Sort by deal_deadline if available, then by title
        for rec in sorted(active_deals, key=lambda r: (r.get("fm", {}).get("deal_deadline", "9999"), r["title"])):
            ctx = build_context_phrase(rec["fm"])
            deadline = rec["fm"].get("deal_deadline", "")
            deadline_str = f", deadline {deadline}" if deadline else ""
            lines.append(f"- [[{rec['path']}|{rec['title']}]] — {ctx}{deadline_str}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # High Priority section (explicit wikilinks)
    if high_priority:
        lines.append(f"## High Priority ({len(high_priority)})")
        lines.append("")
        for rec in sorted(high_priority, key=lambda r: (r["industry"], r["title"])):
            ctx = build_context_phrase(rec["fm"])
            lines.append(f"- [[{rec['path']}|{rec['title']}]] — {ctx}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # By Industry sections
    lines.append("## By Industry")
    lines.append("")

    for industry in sorted_industries:
        industry_records = by_industry[industry]
        lines.append(f"### {industry} ({len(industry_records)})")
        lines.append("")

        # Sort: active/in-work first, then by title
        def sort_key(r: dict) -> tuple:
            status_order = 0
            s = r["status"].lower()
            if s in ("active", "в работе"):
                status_order = 0
            elif "tender" in s or "negotiation" in s:
                status_order = 1
            elif s == "prospect":
                status_order = 2
            else:
                status_order = 3
            return (status_order, r["title"])

        for rec in sorted(industry_records, key=sort_key):
            ctx = build_context_phrase(rec["fm"])
            if ctx:
                lines.append(f"- [[{rec['path']}|{rec['title']}]] — {ctx}")
            else:
                lines.append(f"- [[{rec['path']}|{rec['title']}]]")
        lines.append("")

    # Dataview blocks (preserved at the end)
    lines.extend([
        "---",
        "",
        "## Dataview: Active Deals",
        "",
        "```dataview",
        'TABLE deal_status as "Status", deal_deadline as "Deadline", industry',
        'FROM "business/crm"',
        'WHERE deal_status != null AND deal_status != "StandBy" AND deal_status != "Отказано"',
        "SORT deal_deadline ASC",
        "LIMIT 15",
        "```",
        "",
        "## Dataview: High Priority",
        "",
        "```dataview",
        "TABLE industry, status, deal_status",
        'FROM "business/crm"',
        'WHERE priority = "High"',
        "SORT deal_status DESC",
        "LIMIT 20",
        "```",
        "",
        "## Dataview: By Industry",
        "",
        "```dataview",
        "TABLE WITHOUT ID",
        '  industry as "Industry",',
        '  length(rows) as "Count"',
        'FROM "business/crm"',
        "GROUP BY industry",
        "SORT length(rows) DESC",
        "```",
        "",
        "## Dataview: By Status",
        "",
        "```dataview",
        "TABLE WITHOUT ID",
        '  status as "Status",',
        '  length(rows) as "Count"',
        'FROM "business/crm"',
        "GROUP BY status",
        "SORT length(rows) DESC",
        "```",
        "",
        "## Dataview: Recently Updated",
        "",
        "```dataview",
        "TABLE industry, status, priority",
        'FROM "business/crm"',
        "SORT file.mtime DESC",
        "LIMIT 20",
        "```",
        "",
    ])

    return "\n".join(lines)


def generate_projects_moc() -> str:
    """Generate MOC-projects.md with explicit wikilinks."""

    now = datetime.now().strftime("%Y-%m-%d")

    # Collect clients
    clients: list[dict] = []
    clients_dir = PROJECTS_DIR / "clients"
    if clients_dir.exists():
        for md_file in sorted(clients_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            fm = parse_frontmatter(content)
            title = extract_title(content) or md_file.stem.replace("-", " ").title()
            rel = relative_path(md_file)
            clients.append({
                "path": rel,
                "title": title,
                "industry": fm.get("industry", "Unknown"),
                "status": fm.get("status", ""),
                "region": fm.get("region", ""),
                "company": fm.get("company", title),
                "fm": fm,
            })

    # Collect leads
    leads: list[dict] = []
    leads_dir = PROJECTS_DIR / "leads"
    if leads_dir.exists():
        for md_file in sorted(leads_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            fm = parse_frontmatter(content)
            title = extract_title(content) or md_file.stem.replace("-", " ").title()
            rel = relative_path(md_file)
            leads.append({
                "path": rel,
                "title": title,
                "industry": fm.get("industry", "Unknown"),
                "status": fm.get("status", ""),
                "company": fm.get("company", title),
                "potential": fm.get("potential", ""),
                "region": fm.get("region", ""),
                "fm": fm,
            })

    # Collect projects
    projects: list[dict] = []
    projects_dir = PROJECTS_DIR / "projects"
    if projects_dir.exists():
        for md_file in sorted(projects_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            fm = parse_frontmatter(content)
            title = extract_title(content) or md_file.stem.replace("-", " ").title()
            rel = relative_path(md_file)
            projects.append({
                "path": rel,
                "title": title,
                "status": fm.get("status", ""),
                "fm": fm,
            })

    # Collect standalone files (resources, reports, etc.)
    standalone: list[dict] = []
    for md_file in sorted(PROJECTS_DIR.glob("*.md")):
        if md_file.name == "_index.md":
            continue
        content = md_file.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        title = extract_title(content) or md_file.stem.replace("-", " ").title()
        rel = relative_path(md_file)
        standalone.append({
            "path": rel,
            "title": title,
            "fm": fm,
        })

    # Collect events
    events: list[dict] = []
    events_dir = PROJECTS_DIR / "events"
    if events_dir.exists():
        for md_file in sorted(events_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            fm = parse_frontmatter(content)
            title = extract_title(content) or md_file.stem.replace("-", " ").title()
            rel = relative_path(md_file)
            events.append({
                "path": rel,
                "title": title,
                "status": fm.get("status", ""),
                "fm": fm,
            })

    # Collect reports
    reports: list[dict] = []
    reports_dir = PROJECTS_DIR / "reports"
    if reports_dir.exists():
        for md_file in sorted(reports_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            fm = parse_frontmatter(content)
            title = extract_title(content) or md_file.stem.replace("-", " ").title()
            rel = relative_path(md_file)
            reports.append({
                "path": rel,
                "title": title,
                "fm": fm,
            })

    total = len(clients) + len(leads) + len(projects) + len(standalone) + len(events) + len(reports)

    lines = [
        "# MOC - Projects",
        "",
        "> Map of Content for Projects",
        f"> Generated: {now} | {len(clients)} clients, {len(leads)} leads, {len(projects)} projects",
        "",
        "[[projects/_index|Projects Overview]]",
        "",
        "---",
        "",
    ]

    # Clients
    if clients:
        lines.append(f"## Clients ({len(clients)})")
        lines.append("")
        for rec in sorted(clients, key=lambda r: r["title"]):
            parts = []
            if rec["status"]:
                parts.append(rec["status"])
            if rec["industry"] and rec["industry"] != "Unknown":
                parts.append(rec["industry"])
            if rec["region"]:
                parts.append(rec["region"])
            ctx = ", ".join(parts)
            if ctx:
                lines.append(f"- [[{rec['path']}|{rec['title']}]] — {ctx}")
            else:
                lines.append(f"- [[{rec['path']}|{rec['title']}]]")
        lines.append("")

    # Leads
    if leads:
        # Split into hot/active and others
        hot_leads = [l for l in leads if l["status"].lower() in ("hot", "qualified", "follow-up sent", "proposal sent")]
        other_leads = [l for l in leads if l not in hot_leads]

        lines.append(f"## Leads ({len(leads)})")
        lines.append("")

        if hot_leads:
            lines.append("### Hot / Active")
            lines.append("")
            for rec in sorted(hot_leads, key=lambda r: r["title"]):
                parts = []
                if rec["status"]:
                    parts.append(rec["status"])
                if rec["company"] and rec["company"] != rec["title"]:
                    parts.append(rec["company"])
                if rec["potential"]:
                    parts.append(rec["potential"])
                if rec["region"]:
                    parts.append(rec["region"])
                ctx = ", ".join(parts)
                if ctx:
                    lines.append(f"- [[{rec['path']}|{rec['title']}]] — {ctx}")
                else:
                    lines.append(f"- [[{rec['path']}|{rec['title']}]]")
            lines.append("")

        if other_leads:
            lines.append("### Other Leads")
            lines.append("")
            for rec in sorted(other_leads, key=lambda r: r["title"]):
                parts = []
                if rec["status"]:
                    parts.append(rec["status"])
                if rec["company"] and rec["company"] != rec["title"]:
                    parts.append(rec["company"])
                if rec["potential"]:
                    parts.append(rec["potential"])
                if rec["region"]:
                    parts.append(rec["region"])
                ctx = ", ".join(parts)
                if ctx:
                    lines.append(f"- [[{rec['path']}|{rec['title']}]] — {ctx}")
                else:
                    lines.append(f"- [[{rec['path']}|{rec['title']}]]")
            lines.append("")

    # Projects
    if projects:
        lines.append(f"## Projects ({len(projects)})")
        lines.append("")
        for rec in sorted(projects, key=lambda r: r["title"]):
            status = rec["status"]
            if status:
                lines.append(f"- [[{rec['path']}|{rec['title']}]] — {status}")
            else:
                lines.append(f"- [[{rec['path']}|{rec['title']}]]")
        lines.append("")

    # Events
    if events:
        lines.append(f"## Events ({len(events)})")
        lines.append("")
        for rec in sorted(events, key=lambda r: r["path"]):
            status = rec["status"]
            if status:
                lines.append(f"- [[{rec['path']}|{rec['title']}]] — {status}")
            else:
                lines.append(f"- [[{rec['path']}|{rec['title']}]]")
        lines.append("")

    # Reports
    if reports:
        lines.append(f"## Reports ({len(reports)})")
        lines.append("")
        for rec in sorted(reports, key=lambda r: r["path"]):
            lines.append(f"- [[{rec['path']}|{rec['title']}]]")
        lines.append("")

    # Standalone files
    if standalone:
        lines.append(f"## Resources ({len(standalone)})")
        lines.append("")
        for rec in sorted(standalone, key=lambda r: r["title"]):
            lines.append(f"- [[{rec['path']}|{rec['title']}]]")
        lines.append("")

    # Dataview blocks (preserved)
    lines.extend([
        "---",
        "",
        "## Dataview: Leads",
        "",
        "```dataview",
        "TABLE company, industry, status, responsible",
        'FROM "projects/leads"',
        "SORT updated DESC",
        "```",
        "",
        "## Dataview: Clients",
        "",
        "```dataview",
        "TABLE company, industry, status",
        'FROM "projects/clients"',
        "SORT updated DESC",
        "```",
        "",
    ])

    return "\n".join(lines)


def main():
    """Generate both MOC files."""
    MOC_DIR.mkdir(exist_ok=True)

    # Generate Business MOC
    biz_content = generate_business_moc()
    biz_path = MOC_DIR / "MOC-business.md"
    biz_path.write_text(biz_content, encoding="utf-8")
    print(f"Generated: {biz_path.relative_to(VAULT_PATH)}")

    # Generate Projects MOC
    proj_content = generate_projects_moc()
    proj_path = MOC_DIR / "MOC-projects.md"
    proj_path.write_text(proj_content, encoding="utf-8")
    print(f"Generated: {proj_path.relative_to(VAULT_PATH)}")

    # Stats
    biz_links = biz_content.count("[[")
    proj_links = proj_content.count("[[")
    print(f"\nStats:")
    print(f"  Business: {biz_links} wikilinks")
    print(f"  Projects: {proj_links} wikilinks")
    print(f"  Total:    {biz_links + proj_links} explicit wikilinks")


if __name__ == "__main__":
    main()
