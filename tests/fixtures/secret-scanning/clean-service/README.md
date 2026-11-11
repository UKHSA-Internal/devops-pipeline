# Clean service fixture

A service with no secrets. `make test-pipeline-secrets-clean` runs the standard pipeline against it: Scan must report zero findings and every stage must still pass.
