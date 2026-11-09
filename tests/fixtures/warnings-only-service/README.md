# Warnings-only service fixture

A service whose pipeline settings have warnings but no errors. `make test-pipeline-settings-warnings` runs the standard pipeline against it: Check must pass and the later stages must still run.
