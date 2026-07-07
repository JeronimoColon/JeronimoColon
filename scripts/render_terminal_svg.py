#!/usr/bin/env python3
"""Render assets/terminal.svg for the profile README.

The terminal session is static except for the CHANGELOG block, which shows
the most recent GitHub releases across the pinned repositories. The nightly
workflow in .github/workflows/refresh-readme.yml runs this script and
commits the result when it changes. Any fetch or rendering failure exits
nonzero so the workflow fails visibly instead of publishing a stale or
partial image.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

GITHUB_OWNER = "JeronimoColon"
RELEASE_REPOSITORIES = ("tidesman-mcp", "aws-ses-relay")
CHANGELOG_LINE_COUNT = 3
FETCH_TIMEOUT_SECONDS = 30

# GitHub renders the README column around 900px wide; 78 monospace
# characters at this font size stays inside it, including on mobile.
MAX_LINE_LENGTH = 78

WINDOW_WIDTH = 840
TITLEBAR_HEIGHT = 36
PADDING = 24
LINE_HEIGHT = 22
FONT_SIZE = 14
CHARACTER_WIDTH = 8.4  # monospace advance at FONT_SIZE; used to place the cursor

COLOR_BACKGROUND = "#0c0f14"
COLOR_TITLEBAR = "#161b22"
COLOR_BORDER = "#21262d"
COLOR_TITLE = "#768390"
COLOR_OUTPUT = "#adbac7"
COLOR_BRIGHT = "#e6edf3"
COLOR_PROMPT = "#2dd4bf"
COLOR_NAME = "#4493f8"

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "assets" / "terminal.svg"


class ChangelogError(Exception):
    """Raised when release data cannot be fetched or is unusable."""


@dataclass
class ReleaseEntry:
    repository: str
    name: str
    tag: str
    published_at: str


@dataclass
class Segment:
    text: str
    color: str = COLOR_OUTPUT


# One rendered terminal line; an empty list renders as a blank line.
Row = list[Segment]


def command_row(command: str) -> Row:
    return [Segment("$ ", COLOR_PROMPT), Segment(command, COLOR_BRIGHT)]


def output_row(text: str) -> Row:
    return [Segment(text)]


def truncate(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def fetch_release_entries(repository: str) -> list[ReleaseEntry]:
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{repository}/releases?per_page=5"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{GITHUB_OWNER}-profile-readme",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            releases = json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError) as error:
        raise ChangelogError(f"fetching releases for {repository} failed: {error}") from error

    entries = []
    for release in releases:
        if release.get("draft"):
            continue
        published_at = release.get("published_at")
        if not published_at:
            continue
        entries.append(
            ReleaseEntry(
                repository=repository,
                name=release.get("name") or "",
                tag=release.get("tag_name") or "",
                published_at=published_at,
            )
        )
    return entries


def changelog_line(entry: ReleaseEntry) -> str:
    date = entry.published_at[:10]
    display_name = entry.name or entry.tag

    # "Tidesman v0.1.3" already names the project; a bare "v0.1.0" does not.
    project_label = entry.repository.removesuffix("-mcp")
    if project_label.lower() in display_name.lower():
        title = display_name
    else:
        title = f"{entry.repository} {display_name}"

    return truncate(f"{date}  {title}", MAX_LINE_LENGTH)


def build_changelog_lines(entries: list[ReleaseEntry]) -> list[str]:
    if not entries:
        raise ChangelogError(
            "no published releases found across "
            f"{', '.join(RELEASE_REPOSITORIES)}; refusing to render an empty CHANGELOG"
        )
    newest_first = sorted(entries, key=lambda entry: entry.published_at, reverse=True)
    return [changelog_line(entry) for entry in newest_first[:CHANGELOG_LINE_COUNT]]


def build_session_rows(changelog_lines: list[str]) -> list[Row]:
    rows: list[Row] = [
        command_row("whoami"),
        [
            Segment("Jeronimo Colon III", COLOR_BRIGHT),
            Segment(" - engineering leader, hacking on fun projects. NYC."),
        ],
        [],
        command_row("cat about.txt"),
        output_row("15 years growing & leading high-performing teams: financial services,"),
        output_row("civic tech, B2C & B2B SaaS products, high-traffic travel."),
        output_row("From bio to tech - always thinking in systems."),
        [],
        command_row("ls ~/building"),
        [
            Segment("tidesman/", COLOR_NAME),
            Segment("        a free native MCP server for Apple's container tool"),
        ],
        [
            Segment("aws-ses-relay/", COLOR_NAME),
            Segment("   Rust Lambda that gates and forwards inbound SES mail"),
        ],
        [],
        command_row("printenv STACK"),
        output_row("Rust:TypeScript:Python:Swift:AWS"),
        [],
        command_row("cat sites.txt"),
        [
            Segment("jeronimocolon.com", COLOR_NAME),
            Segment("   portfolio, résumé, and the workshop"),
        ],
        [
            Segment("tidesman.dev", COLOR_NAME),
            Segment("        Tidesman docs and install"),
        ],
        [
            Segment("listmy.info", COLOR_NAME),
            Segment("         what your browser tells the world about you - no tracking"),
        ],
        [],
        command_row(f"tail -n {len(changelog_lines)} CHANGELOG"),
    ]
    rows.extend(output_row(line) for line in changelog_lines)
    rows.append([])
    # Cursor row: the blinking rect is drawn separately in render_svg.
    rows.append([Segment("$ ", COLOR_PROMPT)])
    return rows


def render_svg(rows: list[Row]) -> str:
    for row in rows:
        row_text = "".join(segment.text for segment in row)
        if len(row_text) > MAX_LINE_LENGTH:
            raise ValueError(
                f"terminal line exceeds {MAX_LINE_LENGTH} characters "
                f"({len(row_text)}): {row_text!r}"
            )

    content_top = TITLEBAR_HEIGHT + PADDING
    height = content_top + len(rows) * LINE_HEIGHT + PADDING

    text_elements = []
    for row_index, row in enumerate(rows):
        if not row:
            continue
        baseline = content_top + row_index * LINE_HEIGHT + FONT_SIZE
        tspans = "".join(
            f'<tspan fill="{segment.color}">{escape(segment.text)}</tspan>'
            for segment in row
        )
        text_elements.append(
            f'<text x="{PADDING}" y="{baseline}" xml:space="preserve">{tspans}</text>'
        )

    cursor_row_top = content_top + (len(rows) - 1) * LINE_HEIGHT
    cursor_x = round(PADDING + 2 * CHARACTER_WIDTH)
    cursor = (
        f'<rect x="{cursor_x}" y="{cursor_row_top + 1}" width="8" height="16" '
        f'fill="{COLOR_PROMPT}">'
        '<animate attributeName="opacity" values="1;0" calcMode="discrete" '
        'dur="1.2s" repeatCount="indefinite"/>'
        "</rect>"
    )

    text_block = "\n  ".join(text_elements)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WINDOW_WIDTH}" height="{height}" viewBox="0 0 {WINDOW_WIDTH} {height}" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="{FONT_SIZE}" role="img" aria-label="Terminal session introducing Jeronimo Colon III">
  <defs>
    <clipPath id="window"><rect width="{WINDOW_WIDTH}" height="{height}" rx="10"/></clipPath>
  </defs>
  <g clip-path="url(#window)">
    <rect width="{WINDOW_WIDTH}" height="{height}" fill="{COLOR_BACKGROUND}"/>
    <rect width="{WINDOW_WIDTH}" height="{TITLEBAR_HEIGHT}" fill="{COLOR_TITLEBAR}"/>
    <rect y="{TITLEBAR_HEIGHT - 1}" width="{WINDOW_WIDTH}" height="1" fill="{COLOR_BORDER}"/>
  </g>
  <circle cx="24" cy="18" r="6" fill="#ff5f57"/>
  <circle cx="44" cy="18" r="6" fill="#febc2e"/>
  <circle cx="64" cy="18" r="6" fill="#28c840"/>
  <text x="{WINDOW_WIDTH // 2}" y="22.5" text-anchor="middle" font-size="12" fill="{COLOR_TITLE}">jeronimo@nyc - zsh</text>
  {text_block}
  {cursor}
  <rect x="0.5" y="0.5" width="{WINDOW_WIDTH - 1}" height="{height - 1}" rx="10" fill="none" stroke="{COLOR_BORDER}"/>
</svg>
"""


def main() -> int:
    try:
        entries = []
        for repository in RELEASE_REPOSITORIES:
            entries.extend(fetch_release_entries(repository))
        changelog_lines = build_changelog_lines(entries)
        svg = render_svg(build_session_rows(changelog_lines))
    except (ChangelogError, ValueError) as error:
        print(f"render_terminal_svg: {error}", file=sys.stderr)
        return 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH} with {len(changelog_lines)} changelog lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
