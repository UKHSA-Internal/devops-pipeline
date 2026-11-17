# Approval modes fixture

One service with three settings files, one per `deploy.production.approval_mode`. `make test-pipeline-approval-modes` runs the standard pipeline on a simulated push to `main` for each and asserts which approval jobs run.
