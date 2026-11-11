# Service-with-baseline fixture

Same fake secret as `service-with-finding`, but with a `.secrets.baseline` that already records it. `make test-pipeline-secrets-baseline` runs the standard pipeline against it: Scan must report zero findings because the known secret is suppressed by the baseline.
