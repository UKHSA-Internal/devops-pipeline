import unittest

from scripts.contribution_rules import (
    SCOPES,
    TYPES,
    is_breaking_change,
    validate_adr_gate,
    validate_branch_linkage,
    validate_branch_name,
    validate_commit_message,
    validate_pr_title,
)


class CommitMessageTests(unittest.TestCase):
    def test_every_type_and_scope_is_accepted(self):
        for commit_type in TYPES:
            for scope in SCOPES:
                with self.subTest(commit_type=commit_type, scope=scope):
                    self.assertEqual(
                        validate_commit_message(
                            f"{commit_type}({scope}): implement the change"
                        ),
                        [],
                    )

    def test_cross_cutting_and_repository_scopes_are_accepted(self):
        self.assertEqual(
            validate_commit_message("feat(checker): update shared validation"), []
        )
        self.assertEqual(
            validate_commit_message("chore(repo): update repository tooling"), []
        )
        self.assertEqual(
            validate_commit_message("chore(deps): update dependency"), []
        )

    def test_missing_scope_is_rejected(self):
        self.assertTrue(validate_commit_message("feat: implement the change"))

    def test_invalid_scope_is_rejected(self):
        self.assertTrue(validate_commit_message("feat(workspace): implement change"))

    def test_invalid_type_is_rejected(self):
        self.assertTrue(validate_commit_message("build(repo): update tooling"))

    def test_breaking_marker_and_footer_headers_are_accepted(self):
        self.assertEqual(
            validate_commit_message("feat(workflows)!: change the interface"), []
        )
        self.assertEqual(
            validate_commit_message(
                "feat(workflows): change the interface\n\n"
                "BREAKING CHANGE: update consumer configuration"
            ),
            [],
        )


class BranchAndPullRequestTests(unittest.TestCase):
    def test_branch_with_jira_key_is_accepted(self):
        self.assertEqual(validate_branch_linkage("task/DP-123/add-check", "", []), [])

    def test_branch_without_jira_key_needs_fallback_linkage(self):
        self.assertTrue(validate_branch_linkage("task/add-check", "", []))
        self.assertEqual(
            validate_branch_linkage(
                "task/add-check", "feat(repo): add check (DP-123)", []
            ),
            [],
        )
        self.assertEqual(
            validate_branch_linkage(
                "task/add-check",
                "feat(repo): add check",
                ["feat(repo): add check\n\nRef: DP-123"],
            ),
            [],
        )

    def test_branch_name_types_and_format_are_validated(self):
        for branch_type in ("task", "feature", "fix", "chore", "refactor", "docs"):
            with self.subTest(branch_type=branch_type):
                jira, error = validate_branch_name(
                    f"{branch_type}/DP-123/add-check"
                )
                self.assertEqual(jira, "DP-123")
                self.assertIsNone(error)
        self.assertTrue(validate_branch_name("release/add-check")[1])
        self.assertTrue(validate_branch_name("feature/DP-123/Uppercase")[1])

    def test_pr_title_requires_valid_header_and_jira_key(self):
        self.assertEqual(
            validate_pr_title("fix(checker): correct path parsing (DP-123)"), []
        )
        self.assertTrue(validate_pr_title("fix(workspace): correct path (DP-123)"))
        self.assertTrue(validate_pr_title("fix(checker): correct path"))


class AdrGateTests(unittest.TestCase):
    def test_breaking_change_detects_label_header_and_footer(self):
        self.assertTrue(
            is_breaking_change("feat(repo): change (DP-123)", [], ["breaking-change"])
        )
        self.assertTrue(is_breaking_change("feat(repo)!: change (DP-123)", [], []))
        self.assertTrue(is_breaking_change("feat(workspace)!: change (DP-123)", [], []))
        self.assertTrue(
            is_breaking_change(
                "feat(repo): change (DP-123)",
                ["feat(repo): change\n\nBREAKING CHANGE: migrate consumers"],
                [],
            )
        )
        self.assertTrue(
            is_breaking_change(
                "feat(repo): change (DP-123)",
                ["feat(repo): change\n\nBREAKING CHANGE:"],
                [],
            )
        )
        self.assertFalse(
            is_breaking_change("feat(repo): change (DP-123)", [], [])
        )

    def test_adr_gate_accepts_new_adr(self):
        self.assertEqual(
            validate_adr_gate(True, True, "", [], set()),
            [],
        )

    def test_adr_gate_accepts_reference_existing_on_main(self):
        self.assertEqual(
            validate_adr_gate(
                True,
                False,
                "ADR: docs/adr/0001-existing.md",
                [],
                {"docs/adr/0001-existing.md"},
            ),
            [],
        )
        self.assertEqual(
            validate_adr_gate(
                True,
                False,
                "",
                ["feat(repo): align rules\n\nADR: docs/adr/0001-existing.md"],
                {"docs/adr/0001-existing.md"},
            ),
            [],
        )

    def test_adr_gate_rejects_missing_or_nonexistent_reference(self):
        self.assertTrue(validate_adr_gate(True, False, "", [], set()))
        self.assertTrue(
            validate_adr_gate(
                True,
                False,
                "ADR: docs/adr/9999-not-on-main.md",
                [],
                set(),
            )
        )
        self.assertEqual(validate_adr_gate(False, False, "", [], set()), [])


if __name__ == "__main__":
    unittest.main()
