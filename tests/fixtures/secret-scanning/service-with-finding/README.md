# Service-with-finding fixture

A service containing a clearly fake secret (not a real credential). `make test-pipeline-secrets-finding` runs the standard pipeline against it: Scan must report the finding, but the stage still passes because scanning is report-only.
