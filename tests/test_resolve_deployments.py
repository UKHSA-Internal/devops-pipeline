import importlib.util
import tempfile
import unittest
import unittest.mock
from pathlib import Path

RESOLVER_PATH = (
    Path(__file__).resolve().parents[1]
    / "packages"
    / "shared-workflows"
    / "actions"
    / "resolve-deployments"
    / "resolve_deployments.py"
)
RESOLVER_SPEC = importlib.util.spec_from_file_location("resolve_deployments", RESOLVER_PATH)
if RESOLVER_SPEC is None or RESOLVER_SPEC.loader is None:
    raise ImportError(f"Unable to load deployment resolver from {RESOLVER_PATH}")
RESOLVER = importlib.util.module_from_spec(RESOLVER_SPEC)
RESOLVER_SPEC.loader.exec_module(RESOLVER)


def environment(name, category):
    return {
        "name": name,
        "category": category,
        "account_id": "123456789012",
        "role_name": "pipeline-role",
        "region": "eu-west-2",
    }


def settings(*environments, **overrides):
    return {
        "environments": list(environments)
        or [
            environment("dev-env-1", "Development"),
            environment("preprod-env-1", "Pre-production"),
            environment("prod", "Production"),
        ],
        "service": {"test_command": "python3 -m unittest discover"},
        "verification": {"health_endpoint": "/health", "timeout_seconds": 60},
        "governance": {"approvers": ["platform-leads"]},
        **overrides,
    }


class ResolveDeploymentsTests(unittest.TestCase):
    def test_groups_deployments_by_category(self):
        plan = RESOLVER.resolve(settings())

        self.assertEqual([item["name"] for item in plan["dev_deployments"]], ["dev-env-1"])
        self.assertEqual([item["name"] for item in plan["preprod_deployments"]], ["preprod-env-1"])
        self.assertEqual([item["name"] for item in plan["prod_deployments"]], ["prod"])
        self.assertEqual(plan["health_endpoint"], "/health")
        self.assertEqual(plan["timeout_seconds"], 60)
        self.assertEqual(plan["test_command"], "python3 -m unittest discover")

    def test_supports_multiple_deployments_per_category_in_promotion_order(self):
        plan = RESOLVER.resolve(
            settings(
                environment("prod", "Production"),
                environment("dev-b", "Development"),
                environment("preprod-1", "Pre-production"),
                environment("dev-a", "Development"),
            )
        )

        self.assertEqual([item["name"] for item in plan["dev_deployments"]], ["dev-b", "dev-a"])
        self.assertEqual(
            [item["name"] for item in plan["deployments"]],
            ["dev-b", "dev-a", "preprod-1", "prod"],
        )

    def test_unquoted_account_id_is_kept_as_text(self):
        unquoted = environment("dev-env-1", "Development") | {"account_id": 123456789012}
        plan = RESOLVER.resolve(
            settings(
                unquoted,
                environment("preprod-env-1", "Pre-production"),
                environment("prod", "Production"),
            )
        )

        self.assertEqual(plan["dev_deployments"][0]["account_id"], "123456789012")

    def test_verification_defaults_when_omitted(self):
        values = settings()
        del values["verification"]

        plan = RESOLVER.resolve(values)

        self.assertEqual(plan["health_endpoint"], "/health")
        self.assertEqual(plan["timeout_seconds"], 60)

    def test_falls_back_to_defaults_when_verification_is_not_a_mapping(self):
        plan = RESOLVER.resolve(settings(verification="none"))

        self.assertEqual(plan["health_endpoint"], "/health")
        self.assertEqual(plan["timeout_seconds"], 60)

    def test_language_is_normalised_to_lower_case(self):
        values = settings()
        values["service"]["language"] = "  Python  "

        self.assertEqual(RESOLVER.resolve(values)["language"], "python")

    def test_language_keeps_internal_whitespace(self):
        values = settings()
        values["service"]["language"] = " Py Thon "

        self.assertEqual(RESOLVER.resolve(values)["language"], "py thon")

    def test_language_is_empty_when_missing_or_not_text(self):
        self.assertEqual(RESOLVER.resolve(settings())["language"], "")

        values = settings()
        values["service"]["language"] = None

        self.assertEqual(RESOLVER.resolve(values)["language"], "")

    def test_outputs_are_delimited_so_values_cannot_add_outputs(self):
        plan = RESOLVER.resolve(
            settings(verification={"health_endpoint": "/health\ntest_command=injected", "timeout_seconds": 60})
        )
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "output"
            RESOLVER.write_outputs(plan, output_path)
            lines = output_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(sum(line.startswith("test_command<<") for line in lines), 1)
        self.assertIn("test_command=injected", lines)
        self.assertTrue(lines[0].startswith("test_command<<EOF_"))


class ResolveApprovalTests(unittest.TestCase):
    def approval(self, mode=None, approvers=("platform-leads", "security-leads"), **production):
        deploy = {"production": {**({"approval_mode": mode} if mode else {}), **production}}
        return RESOLVER.resolve(
            settings(deploy=deploy, governance={"approvers": list(approvers)})
        )

    def test_all_approvers_has_one_environment_per_group(self):
        plan = self.approval("all-approvers")

        self.assertEqual(plan["approval_mode"], "all-approvers")
        self.assertEqual(
            plan["approval_environments"],
            [
                {"environment": "production-approval-platform-leads", "groups": ["platform-leads"]},
                {"environment": "production-approval-security-leads", "groups": ["security-leads"]},
            ],
        )

    def test_mode_defaults_to_all_approvers(self):
        plan = RESOLVER.resolve(settings(governance={"approvers": ["platform-leads"]}))

        self.assertEqual(plan["approval_mode"], "all-approvers")
        self.assertEqual(len(plan["approval_environments"]), 1)

    def test_single_approver_has_one_environment_for_all_groups(self):
        plan = self.approval("single-approver")

        self.assertEqual(
            plan["approval_environments"],
            [{"environment": "production-approval", "groups": ["platform-leads", "security-leads"]}],
        )

    def test_unattended_has_no_environments_and_keeps_the_exception_id(self):
        plan = self.approval("unattended", exception_id=" EXC-0001 ")

        self.assertEqual(plan["approval_environments"], [])
        self.assertEqual(plan["approval_exception_id"], "EXC-0001")

    def test_unattended_ignores_unusable_group_names(self):
        plan = self.approval("unattended", approvers=("not a valid name!",), exception_id="EXC-1")

        self.assertEqual(plan["approval_environments"], [])

    def test_rejects_group_names_that_cannot_be_environment_names(self):
        for group in ("has space", "-leading-dash", "slash/name", "x" * 300):
            with self.subTest(group=group), self.assertRaisesRegex(ValueError, "cannot be used"):
                self.approval("all-approvers", approvers=(group,))

    def test_rejects_groups_that_differ_only_by_case(self):
        with self.assertRaisesRegex(ValueError, "more than once"):
            self.approval("single-approver", approvers=("Platform-Leads", "platform-leads"))

    def test_rejects_missing_approvers_when_a_gate_is_needed(self):
        with self.assertRaisesRegex(ValueError, "at least one approver group"):
            self.approval("all-approvers", approvers=())

    def test_main_reports_invalid_groups_as_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pipeline-settings.yml"
            path.write_text(
                "environments: []\nservice: {test_command: x}\ngovernance: {approvers: ['bad name']}\n",
                encoding="utf-8",
            )
            with unittest.mock.patch.object(RESOLVER.sys, "argv", ["resolve", str(path)]):
                self.assertEqual(RESOLVER.main(), 1)


if __name__ == "__main__":
    unittest.main()
