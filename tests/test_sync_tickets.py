from __future__ import annotations

import unittest

from scripts.sync_tickets import GitHubTicketSync, IssueData


class TestSyncTicketMapping(unittest.TestCase):
    def test_build_macro_issue_mapping_groups_by_macro_and_kind(self) -> None:
        sync = GitHubTicketSync("owner", "repo", token="dummy")
        issues: list[IssueData] = [
            {
                "number": 4,
                "title": "MACRO-004 - Intelligence generale via Leon",
                "state": "open",
                "html_url": "https://example/4",
                "labels": [{"name": "macro"}, {"name": "macro-004"}],
            },
            {
                "number": 29,
                "title": "MACRO-004-T1 - Stabiliser le contrat d'appel Leon",
                "state": "closed",
                "html_url": "https://example/29",
                "labels": [{"name": "task"}, {"name": "macro-004"}],
            },
            {
                "number": 99,
                "title": "Issue sans macro",
                "state": "open",
                "html_url": "https://example/99",
                "labels": [{"name": "bug"}],
            },
        ]

        mapping = sync.build_macro_issue_mapping(issues)
        macro = mapping["macros"]["MACRO-004"]

        self.assertEqual(macro["counts"]["total"], 2)
        self.assertEqual(macro["counts"]["open"], 1)
        self.assertEqual(macro["counts"]["closed"], 1)
        self.assertEqual(macro["issues"]["macro"][0]["number"], 4)
        self.assertEqual(macro["issues"]["task"][0]["number"], 29)
        self.assertEqual(mapping["unmatched_issues"], [99])


if __name__ == "__main__":
    unittest.main()
