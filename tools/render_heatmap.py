#!/usr/bin/env python3
"""Render the contribution calendar (last 12 months) as a warm SVG.

The data comes straight from the GitHub GraphQL API for the authenticated
user, so it matches the contribution graph on the profile page. The result is
committed as assets/contributions.svg and embedded in the profile README.

Usage:
    GITHUB_TOKEN=ghp_xxx python3 tools/render_heatmap.py
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

USER = "DiovaniFacco"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "contributions.svg"

# hot palette: empty .. busiest
PALETTE = ["#161B22", "#5A2109", "#A33C0C", "#E8631A", "#FFB347"]
BG = "#0D1117"
TEXT = "#8B949E"

CELL = 11
GAP = 3
STEP = CELL + GAP

QUERY = """
query {
  viewer {
    contributionsCollection {
      contributionCalendar {
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
  }
}
"""


def token() -> str:
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(key):
            return os.environ[key]
    creds = Path.home() / ".git-credentials"
    if creds.exists():
        match = re.search(r"https://[^:]*:([^@]*)@", creds.read_text())
        if match:
            return match.group(1)
    sys.exit("No GitHub token found (set GITHUB_TOKEN).")


def fetch(login: str) -> list[list[dict]]:
    payload = json.dumps({"query": QUERY})
    proc = subprocess.run(
        [
            "curl",
            "-s",
            "-X",
            "POST",
            "-H",
            f"Authorization: bearer {token()}",
            "-H",
            "Content-Type: application/json",
            "https://api.github.com/graphql",
            "--data-binary",
            "@-",
        ],
        input=payload,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(proc.stdout)
    if "errors" in data:
        sys.exit(data["errors"])
    weeks = data["data"]["viewer"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [week["contributionDays"] for week in weeks]


def level(count: int, thresholds: list[int]) -> int:
    if count <= 0:
        return 0
    for index, bound in enumerate(thresholds):
        if count <= bound:
            return index + 1
    return 4


def render(weeks: list[list[dict]]) -> str:
    counts = [day["contributionCount"] for week in weeks for day in week]
    positive = sorted(c for c in counts if c > 0)
    if positive:
        q = lambda p: positive[min(len(positive) - 1, int(len(positive) * p))]
        thresholds = [q(0.25), q(0.5), q(0.75)]
    else:
        thresholds = [1, 2, 3]

    left = 30
    top = 22
    width = left + len(weeks) * STEP + 24
    height = top + 7 * STEP + 34

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif">',
        f'<rect width="{width}" height="{height}" rx="6" fill="{BG}"/>',
    ]

    # month labels
    seen = None
    for index, week in enumerate(weeks):
        if not week:
            continue
        first = dt.date.fromisoformat(week[0]["date"])
        if first.month != seen:
            seen = first.month
            x = left + index * STEP
            parts.append(
                f'<text x="{x}" y="{top - 8}" font-size="10" fill="{TEXT}">{first.strftime("%b")}</text>'
            )

    # weekday labels
    for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        y = top + row * STEP + CELL - 2
        parts.append(f'<text x="0" y="{y}" font-size="10" fill="{TEXT}">{label}</text>')

    # cells
    for col, week in enumerate(weeks):
        for day in week:
            date = dt.date.fromisoformat(day["date"])
            row = (date.weekday() + 1) % 7  # Sunday first
            x = left + col * STEP
            y = top + row * STEP
            fill = PALETTE[level(day["contributionCount"], thresholds)]
            parts.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{fill}">'
                f"<title>{day['date']}: {day['contributionCount']}</title></rect>"
            )

    # legend
    ly = top + 7 * STEP + 14
    parts.append(f'<text x="{left}" y="{ly + 9}" font-size="10" fill="{TEXT}">Less</text>')
    lx = left + 32
    for shade in PALETTE:
        parts.append(
            f'<rect x="{lx}" y="{ly}" width="{CELL}" height="{CELL}" rx="2" fill="{shade}"/>'
        )
        lx += STEP
    parts.append(f'<text x="{lx + 4}" y="{ly + 9}" font-size="10" fill="{TEXT}">More</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    weeks = fetch(USER)
    total = sum(day["contributionCount"] for week in weeks for day in week)
    active = sum(1 for week in weeks for day in week if day["contributionCount"] > 0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(weeks), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} — {total} contributions on {active} active days")


if __name__ == "__main__":
    main()
