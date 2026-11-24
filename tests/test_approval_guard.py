import io
import os
import sys
import unittest
import unittest.mock
import urllib.error
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import ACTIONS, load_script

GUARD = load_script(ACTIONS / "approval-guard" / "approval_guard.py", "approval_guard")
CONFIRM = load_script(ACTIONS / "approval-confirm" / "approval_confirm.py", "approval_confirm")


def gated(name, reviewers=1, prevent_self_review=True, can_admins_bypass=False):
    return {
        "name": name,
        "can_admins_bypass": can_admins_bypass,
        "protection_rules": [
            {
                "type": "required_reviewers",
                "prevent_self_review": prevent_self_review,
                "reviewers": [{"type": "Team"}] * reviewers,
            }
        ],
    }


def keyed(*environments):
    return {environment["name"].lower(): environment for environment in environments}


class EvaluateTests(unittest.TestCase):
    def test_gated_environment_passes_without_warnings(self):
        errors, warnings = GUARD.evaluate(["production-approval-a"], keyed(gated("production-approval-a")))

        self.assertEqual((errors, warnings), ([], []))

    def test_missing_environment_is_an_error(self):
        errors, _ = GUARD.evaluate(["production-approval-a"], {})

        self.assertEqual(len(errors), 1)
        self.assertIn("does not exist", errors[0])

    def test_environment_name_match_ignores_case(self):
        errors, _ = GUARD.evaluate(["production-approval-Leads"], keyed(gated("Production-Approval-leads")))

        self.assertEqual(errors, [])

    def test_environment_without_reviewers_is_an_error(self):
        for environment in (
            gated("production-approval", reviewers=0),
            {"name": "production-approval", "protection_rules": []},
            {"name": "production-approval", "protection_rules": [{"type": "wait_timer"}]},
            {"name": "production-approval", "protection_rules": None},
        ):
            with self.subTest(environment=environment):
                errors, _ = GUARD.evaluate(["production-approval"], keyed(environment))
                self.assertEqual(len(errors), 1)
                self.assertIn("no required reviewers", errors[0])

    def test_self_review_allowed_is_an_error(self):
        errors, _ = GUARD.evaluate(["production-approval"], keyed(gated("production-approval", prevent_self_review=False)))

        self.assertEqual(len(errors), 1)
        self.assertIn("self-review", errors[0])

    def test_admin_bypass_is_only_a_warning(self):
        errors, warnings = GUARD.evaluate(
            ["production-approval"], keyed(gated("production-approval", can_admins_bypass=True))
        )

        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("bypass", warnings[0])

    def test_every_expected_environment_is_checked(self):
        errors, _ = GUARD.evaluate(["a", "b", "c"], keyed(gated("a"), gated("c", reviewers=0)))

        self.assertEqual(len(errors), 2)


class FetchTests(unittest.TestCase):
    def test_reads_every_page(self):
        pages = {
            1: {"environments": [{"name": f"env-{index}"} for index in range(100)]},
            2: {"environments": [{"name": "Production-Approval"}]},
        }
        urls = []

        def get(url, token):
            urls.append(url)
            return pages[int(url.rsplit("page=", 1)[1])]

        environments = GUARD.fetch_environments("owner/repo", "token", get=get)

        self.assertEqual(len(environments), 101)
        self.assertIn("production-approval", environments)
        self.assertEqual(len(urls), 2)

    def test_unreadable_environments_fail_with_the_prerequisites(self):
        for code in (401, 403, 404):
            error = urllib.error.HTTPError("url", code, "denied", {}, None)
            with self.subTest(code=code), unittest.mock.patch.object(
                GUARD.urllib.request, "urlopen", side_effect=error
            ), self.assertRaisesRegex(GUARD.GuardError, "actions: read"):
                GUARD.request("https://api.github.com/x", "token")

    def test_server_errors_are_retried_then_fail(self):
        error = urllib.error.HTTPError("url", 502, "bad gateway", {}, None)
        with unittest.mock.patch.object(GUARD.urllib.request, "urlopen", side_effect=error) as urlopen, \
                unittest.mock.patch.object(GUARD.time, "sleep"), \
                self.assertRaisesRegex(GUARD.GuardError, "after 3 attempts"):
            GUARD.request("https://api.github.com/x", "token")

        self.assertEqual(urlopen.call_count, 3)


class GuardMainTests(unittest.TestCase):
    def run_main(self, plan, environments=None, error=None, act=False):
        env = {"APPROVAL_ENVIRONMENTS": plan, "REPOSITORY": "owner/repo", "GH_TOKEN": "t", "ACT": "true" if act else ""}
        fetch = unittest.mock.patch.object(
            GUARD, "fetch_environments", side_effect=error, return_value=environments
        )
        output = io.StringIO()
        with unittest.mock.patch.dict(os.environ, env), fetch, redirect_stdout(output):
            status = GUARD.main()
        return status, output.getvalue()

    def test_unattended_expects_nothing_and_never_calls_the_api(self):
        status, output = self.run_main("[]")

        self.assertEqual(status, 0)
        self.assertIn("unattended", output)

    def test_unreadable_environments_fail_closed(self):
        status, output = self.run_main(
            '[{"environment":"production-approval","groups":["a"]}]', error=GUARD.GuardError("denied")
        )

        self.assertEqual(status, 1)
        self.assertIn("::error", output)

    def test_missing_environment_fails(self):
        status, _ = self.run_main('[{"environment":"production-approval","groups":["a"]}]', environments={})

        self.assertEqual(status, 1)

    def test_gated_environments_pass(self):
        status, output = self.run_main(
            '[{"environment":"production-approval","groups":["a"]}]',
            environments=keyed(gated("production-approval")),
        )

        self.assertEqual(status, 0)
        self.assertIn("[STEP: APPROVAL] Guard passed", output)

    def test_act_skips_the_api(self):
        status, output = self.run_main(
            '[{"environment":"production-approval","groups":["a"]}]', error=AssertionError("called"), act=True
        )

        self.assertEqual(status, 0)
        self.assertIn("skipped under act", output)


class ConfirmTests(unittest.TestCase):
    NOW = datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone.utc)

    def test_approval_within_the_window_is_accepted(self):
        self.assertFalse(CONFIRM.is_expired("2026-11-16T12:00:01Z", self.NOW, 24))

    def test_approval_exactly_at_the_limit_is_accepted(self):
        self.assertFalse(CONFIRM.is_expired("2026-11-16T12:00:00Z", self.NOW, 24))

    def test_approval_after_the_window_is_expired(self):
        self.assertTrue(CONFIRM.is_expired("2026-11-16T11:59:59Z", self.NOW, 24))

    def run_main(self, opened_at):
        env = {
            "APPROVAL_ENVIRONMENT": "production-approval-a",
            "APPROVAL_GROUPS": "a",
            "GATE_OPENED_AT": opened_at,
            "MAX_AGE_HOURS": "24",
        }
        output = io.StringIO()
        with unittest.mock.patch.dict(os.environ, env), redirect_stdout(output):
            return CONFIRM.main(), output.getvalue()

    def test_main_logs_the_marker_naming_the_group(self):
        status, output = self.run_main(datetime.now(timezone.utc).strftime(CONFIRM.TIME_FORMAT))

        self.assertEqual(status, 0)
        self.assertIn("[STEP: APPROVAL] production-approval-a approved for group(s): a", output)

    def test_main_rejects_an_expired_approval(self):
        status, output = self.run_main("2020-01-01T00:00:00Z")

        self.assertEqual(status, 1)
        self.assertIn("EXPIRED", output)

    def test_main_fails_closed_on_an_unreadable_time(self):
        status, _ = self.run_main("")

        self.assertEqual(status, 1)


if __name__ == "__main__":
    unittest.main()
