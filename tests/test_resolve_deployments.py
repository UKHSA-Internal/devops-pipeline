import importlib.util
import unittest
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
            environment("dev-env-1", "Dev"),
            environment("preprod-env-1", "Pre-production"),
            environment("prod", "Production"),
        ],
        "service": {"test_command": "python3 -m unittest discover"},
        "verification": {"health_endpoint": "/health", "timeout_seconds": 60},
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
                environment("dev-b", "Dev"),
                environment("preprod-1", "Pre-production"),
                environment("dev-a", "Dev"),
            )
        )

        self.assertEqual([item["name"] for item in plan["dev_deployments"]], ["dev-b", "dev-a"])
        self.assertEqual(
            [item["name"] for item in plan["deployments"]],
            ["dev-b", "dev-a", "preprod-1", "prod"],
        )

    def test_unquoted_account_id_is_kept_as_text(self):
        unquoted = environment("dev-env-1", "Dev") | {"account_id": 123456789012}
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

    def test_rejects_invalid_settings(self):
        cases = {
            "no environments": {"environments": []},
            "missing category": settings(
                environment("dev-env-1", "Dev"), environment("preprod-env-1", "Pre-production")
            ),
            "unknown category": settings(environment("dev-env-1", "Staging")),
            "duplicate name": settings(
                environment("same", "Dev"),
                environment("same", "Pre-production"),
                environment("prod", "Production"),
            ),
            "unsafe name": settings(environment("../dev", "Dev")),
            "missing field": settings(environment("dev-env-1", "Dev") | {"role_name": ""}),
            "relative health endpoint": settings(
                verification={"health_endpoint": "health", "timeout_seconds": 60}
            ),
            "missing test command": settings(service={"name": "sample-app"}),
            "blank test command": settings(service={"test_command": "  "}),
            "multiline test command": settings(service={"test_command": "a\nb"}),
            "bad timeout": settings(
                verification={"health_endpoint": "/health", "timeout_seconds": 0}
            ),
        }
        for label, invalid in cases.items():
            with self.subTest(label), self.assertRaises(RESOLVER.SettingsError):
                RESOLVER.resolve(invalid)


if __name__ == "__main__":
    unittest.main()
