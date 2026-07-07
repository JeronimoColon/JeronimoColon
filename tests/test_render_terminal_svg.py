import sys
import unittest
import xml.etree.ElementTree
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import render_terminal_svg as renderer

SAMPLE_CHANGELOG_LINES = [
    "2026-07-06  aws-ses-relay v0.1.0",
    "2026-07-05  Tidesman v0.1.3",
    "2026-07-05  Tidesman v0.1.2",
]


def sample_entry(**overrides):
    fields = {
        "repository": "tidesman-mcp",
        "name": "Tidesman v0.1.3",
        "tag": "v0.1.3",
        "published_at": "2026-07-05T20:05:52Z",
    }
    fields.update(overrides)
    return renderer.ReleaseEntry(**fields)


class ChangelogLineTests(unittest.TestCase):
    def test_uses_release_name_when_it_names_the_project(self):
        entry = sample_entry()
        self.assertEqual(renderer.changelog_line(entry), "2026-07-05  Tidesman v0.1.3")

    def test_prefixes_repository_when_name_is_a_bare_version(self):
        entry = sample_entry(
            repository="aws-ses-relay",
            name="v0.1.0",
            tag="v0.1.0",
            published_at="2026-07-06T16:10:56Z",
        )
        self.assertEqual(renderer.changelog_line(entry), "2026-07-06  aws-ses-relay v0.1.0")

    def test_falls_back_to_tag_when_name_is_empty(self):
        entry = sample_entry(name="", tag="v0.2.0")
        self.assertEqual(renderer.changelog_line(entry), "2026-07-05  tidesman-mcp v0.2.0")

    def test_truncates_overlong_titles_to_the_line_limit(self):
        entry = sample_entry(name="Tidesman " + "x" * 200)
        line = renderer.changelog_line(entry)
        self.assertEqual(len(line), renderer.MAX_LINE_LENGTH)
        self.assertTrue(line.endswith("..."))


class BuildChangelogLinesTests(unittest.TestCase):
    def test_sorts_newest_first_and_keeps_three(self):
        entries = [
            sample_entry(name="Tidesman v0.1.1", published_at="2026-07-03T04:27:39Z"),
            sample_entry(
                repository="aws-ses-relay",
                name="v0.1.0",
                tag="v0.1.0",
                published_at="2026-07-06T16:10:56Z",
            ),
            sample_entry(name="Tidesman v0.1.3", published_at="2026-07-05T20:05:52Z"),
            sample_entry(name="Tidesman v0.1.0", published_at="2026-07-01T07:55:47Z"),
        ]
        lines = renderer.build_changelog_lines(entries)
        self.assertEqual(
            lines,
            [
                "2026-07-06  aws-ses-relay v0.1.0",
                "2026-07-05  Tidesman v0.1.3",
                "2026-07-03  Tidesman v0.1.1",
            ],
        )

    def test_raises_when_there_are_no_entries(self):
        with self.assertRaises(renderer.ChangelogError):
            renderer.build_changelog_lines([])


class RenderSvgTests(unittest.TestCase):
    def render_sample(self):
        rows = renderer.build_session_rows(SAMPLE_CHANGELOG_LINES)
        return renderer.render_svg(rows)

    def test_output_is_well_formed_xml(self):
        xml.etree.ElementTree.fromstring(self.render_sample())

    def test_escapes_ampersands_in_session_text(self):
        svg = self.render_sample()
        self.assertIn("B2C &amp; B2B", svg)

    def test_includes_blinking_cursor_animation(self):
        self.assertIn("<animate", self.render_sample())

    def test_includes_changelog_lines(self):
        svg = self.render_sample()
        for line in SAMPLE_CHANGELOG_LINES:
            self.assertIn(line, svg)

    def test_every_session_row_fits_the_line_limit(self):
        rows = renderer.build_session_rows(SAMPLE_CHANGELOG_LINES)
        for row in rows:
            row_text = "".join(segment.text for segment in row)
            self.assertLessEqual(len(row_text), renderer.MAX_LINE_LENGTH, row_text)

    def test_rejects_rows_over_the_line_limit(self):
        overlong_row = [renderer.Segment("x" * (renderer.MAX_LINE_LENGTH + 1))]
        with self.assertRaises(ValueError):
            renderer.render_svg([overlong_row])


if __name__ == "__main__":
    unittest.main()
