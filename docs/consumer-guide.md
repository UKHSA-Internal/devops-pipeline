# Using the shared pipeline

This guide is for service teams adopting the pipeline. For the settings
contract, rules and checker options, see the
[settings checker reference](../packages/settings-checker/README.md).

## Prerequisites

The platform repository's Actions access must be set to organisation level
(Settings, Actions, General, Access). GitHub can then fetch the release's
pinned composite actions for consumers without a separate checkout token.

Use the floating major tag (`@v1`) for automatic updates, or an exact version
tag (for example `@v1.0.0`) for a fixed release. `@v0` stays on the last 0.x
release and no longer receives updates; callers on `@v0` should move to `@v1`.

## Add a caller

Create `.github/workflows/pipeline.yml` in the service repository. See the
[tested example caller](examples/caller-workflow.yml) for a complete file,
including the `contents: read` and `id-token: write` permissions Deploy needs
for OIDC and the optional `settings_path` input.

The [app-template caller](../packages/app-template/.github/workflows/pipeline.yml)
uses the same `uses:` reference. The workflow reference must be literal.

## Configure the service

Start with the [app-template settings](../packages/app-template/.github/pipeline-settings.yml)
at `.github/pipeline-settings.yml`. Replace placeholder service information,
accounts, roles and approvers with the service's values. Provide at least one
environment in each of Development, Pre-production and Production.

The Check stage flags unreplaced placeholders and malformed account IDs, so
copying the template without editing it does not pass unnoticed: each
`account_id` must be the service's real 12-digit account ID, not all zeros
(CHK-03), and no field may still contain `replace-with-` or `TODO` text
(CHK-13, a warning).

`service.test_command` must be a non-empty, single-line command. The template's
`python3 -m unittest discover -s tests -v` runs a placeholder test: replace the
placeholder with the service's real tests. The
[sample app](../sample-app/README.md) shows a working example.

### Test runtime

The Test stage sets up a language runtime before running `test_command`, based
on `service.language`. The runner has no particular version pre-installed, so
the service must declare the version it needs:

| `service.language` | Version file in the service directory | Runtime |
| --- | --- | --- |
| `python` | `.python-version` | `actions/setup-python` |
| `node` | `.nvmrc`, or `.node-version` | `actions/setup-node` |

`python` and `node` are the only accepted values. Matching ignores case and
surrounding whitespace. If the language is `python` or `node` and its version
file is missing, the Test stage fails and names the file to add. Any other
value, or no value at all, sets up no runtime: the Test stage logs a warning
and runs `test_command` on the runner as it is, so the command must rely only
on what the runner already provides.

The workflow uses `.github/pipeline-settings.yml` by default. For a service in a
subdirectory, set the reusable workflow's `settings_path` input to its settings
file. If no input or root settings file is present, the workflow accepts exactly
one `*/.github/pipeline-settings.yml` file. The test command runs from the
service directory.

Check settings locally before onboarding:

```bash
pip install -r packages/settings-checker/requirements.txt
python3 packages/settings-checker/checker.py ../my-service
```

Run these commands from a checkout of this platform repository. The checker
reports errors and warnings; its default mode fails on errors. Use `--strict`
to fail on warnings too. See the [checker reference](../packages/settings-checker/README.md)
for the complete contract and options.

## What the pipeline does

The Check stage validates settings, then the pipeline sets up the service's
language runtime and runs the configured test command and placeholder scan.
Pushes additionally build, deploy and verify the service; pull requests stop
after Scan, so they never build an image or deploy. It records a run report
and passes the full-commit-SHA image tag to each deployment. Deployments
within each category run one at a time in settings order. Pushes deploy to
Development; Pre-production and Production run only on pushes to `main`.

<!-- TODO: Pull requests may deploy to an ephemeral environment in future. -->

## Production approval

After Pre-production, the pipeline stops and waits for people to approve
before it deploys to Production. The Production deploy runs only after every
approval succeeds. A rejected, cancelled or failed approval never lets it run.
Pull requests never reach this point: only a push to `main` does.

To set it up: choose a mode, set it in your settings, create the GitHub
environments, grant `actions: read` in the caller, then work through the
[checklist](#checklist-before-the-first-merge-to-main). Run record fields and
error messages are in the [reference](#production-approval-reference) at the end.

### Choose a mode

Set `deploy.production.approval_mode`. The Settings Check tool requires the
field (CHK-09). The default mode is `all-approvers`.

| Mode | Use it when | Approval gates |
| --- | --- | --- |
| `all-approvers` (default) | Every approver group must sign off. | One per group, run in parallel. |
| `single-approver` | One sign-off from any of the groups is enough. | One, shared by all groups. |
| `unattended` | Production must deploy with no human pause. | None. |

`unattended` needs `deploy.production.exception_id` (CHK-10). Get an approved
Architecture Exception first and use its ID. The Settings Check tool only
checks that the field is not blank. It does not check that the exception was
approved. The pipeline records the ID in the run record.

### Settings

`governance.approvers` lists the approver groups. It must be a non-empty list
and must include `service.owner_team` (CHK-05). Names are compared ignoring
case. The owner team stands in for the platform approver configuration until
that exists.

Group names become part of a GitHub environment name. Use only letters,
digits, `.`, `_` and `-`, starting with a letter or digit, at most 235
characters. A name that is listed twice, ignoring case, fails Check.

```yaml
service:
  owner_team: "platform-leads"
governance:
  approvers: ["platform-leads", "security-leads"]
deploy:
  production:
    approval_mode: "all-approvers"   # or "single-approver" or "unattended"
    # exception_id: "EXC-0001"       # unattended only: your approved Architecture Exception ID
```

Only `approval_mode` and `exception_id` change between modes.
`service.owner_team` and `governance.approvers` must pass CHK-05 in every mode.

### Create the GitHub environments

Do this in the service repository before the first run on `main`. You need
`admin` access to the repository.

Required reviewers work on a public repository, or on a private or internal
repository on GitHub Team or Enterprise. See GitHub's
[environments documentation](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).

1. Work out the environment names:

   | Mode | Environments to create |
   | --- | --- |
   | `all-approvers` | One per group in `governance.approvers`: `production-approval-<group>`. For `platform-leads`, that is `production-approval-platform-leads`. |
   | `single-approver` | One: `production-approval`. |
   | `unattended` | None. |

   Names are not case sensitive.
2. In the repository, go to **Settings**, then **Environments**, then
   **New environment**. Enter the name.
3. Select **Required reviewers**. Add the GitHub team for the group as the
   required reviewer. For `single-approver`, add the GitHub team for each group
   that may approve. GitHub allows up to 6 people or teams per environment. A
   team counts as one. Only one of the reviewers needs to approve.
4. Select **Prevent self-review**, then **Save protection rules**.
5. Repeat for each environment.

Prevent self-review must be on. The person who triggered the run cannot
approve it. On `main` that is the person who pushed or merged. So each
reviewer team needs at least two people, or nobody can approve that person's
change.

Administrators can bypass an environment's protection rules unless you turn
that off. The guard only warns about this. It does not fail the run. To close
the gap, clear **Allow administrators to bypass configured protection rules**
on each approval environment.

The guard checks, for each environment it expects:

- the environment exists;
- it has at least one required reviewer;
- a required-reviewers rule has Prevent self-review on;
- administrators cannot bypass it (a warning only).

The guard does not check who the reviewers are, whether they are teams, or
whether a team matches its group.

### Grant permissions in the caller workflow

The caller workflow must grant `actions: read`, as the
[example caller](examples/caller-workflow.yml) does. It also needs
`contents: read` and `id-token: write`. Keep `actions: read` in every mode.
Under `unattended` nothing reads the API, but the example grants it so a
change of mode needs no workflow change.

- The approval guard uses `actions: read` to read the environment settings. It
  fails the run before Production without it.
- The report job uses it to read the approval history. Without it the run
  record is still written, but it has `approvals_unavailable: true` and no
  approver details.

### What happens in a run

1. The pipeline runs Check, Test, Scan, Build, Development and
   Pre-production on its own.
2. The approval guard runs. If an environment is missing or unprotected, the
   run fails here, before Production.
3. The run shows "Waiting" with one gate per environment. Under `all-approvers`
   the gates wait in parallel. Under `unattended` there is no pause.
4. A reviewer opens the run and uses **Review deployments**. Only the people
   or teams set as required reviewers on that environment can approve. Anyone
   else cannot. The person who triggered the run cannot approve it.
5. Under `all-approvers`, each group approves its own environment, and one
   reviewer per group is enough. Production runs when all groups have
   approved.
6. Each approval writes a `[STEP: APPROVAL]` line to the log naming its group.

Time limit:

- An approval given more than 24 hours after the gate opened is refused. The
  leg fails with "Approval expired", and Production does not run. To try
  again, start a new run (a push to `main`), or use "Re-run all jobs".
  "Re-run failed jobs" reuses the original gate time and expires again.
- The run is not cancelled automatically. A run nobody acts on stays waiting,
  up to GitHub's own limit. Cancel stale runs yourself.
- A newer run of the same service replaces an older run still waiting at the
  same gate. "Same service" means the same repository and the same
  `settings_path`. A run for a different settings file in the same repository
  is not replaced.

If a reviewer rejects, the other waiting gates are cancelled and Production
does not run.

### Checklist before the first merge to `main`

- [ ] `governance.approvers` lists the groups and includes `service.owner_team`.
- [ ] `deploy.production.approval_mode` is set. For `unattended`, an approved
      exception ID is in `deploy.production.exception_id`.
- [ ] The approval environments exist, named as in the table above.
- [ ] Each has the group's GitHub team as a required reviewer.
- [ ] Prevent self-review is on, and each team has at least two people.
- [ ] The caller workflow grants `actions: read`, `contents: read` and
      `id-token: write`.
- [ ] The repository is public, or private or internal on GitHub Team or
      Enterprise, so required reviewers work.
- [ ] The people who can approve know that stale waiting runs need cancelling.

## Production approval reference

### What the run record shows

The `governance` block of
[run-record.json](examples/run-record.json) records the approval.
`approvers` has one entry per decision: `environment`, `groups`, `approver`,
`decision` and `timestamp`. `decision` is `approved`, `rejected` or `expired`.

| Case | `approval_mode` | `exception_id` | `approvers` |
| --- | --- | --- | --- |
| All groups approved | `all-approvers` | `null` | One `approved` entry per group. |
| One approval gate approved | `single-approver` | `null` | One `approved` entry. |
| No pause | `unattended` | The exception ID | Empty list. |
| Approval history could not be read | The mode | As above | `null`, with `approvals_unavailable: true`. |

How the timestamp is set: an approved or expired entry uses the time the
approval leg started, which is after the approval. A rejected entry uses the
time the leg ended.

When approval stops Production:

- `steps.deploy` is `FAILED`.
- The Production entries in `environments` are `SKIPPED`, with a
  `skipped_reason`.
- A rejected approval gives `approval rejected by <user> (<environment>)`.
- An expired approval gives `approval expired (<environment>)`. An entry is
  `expired` only when the leg started more than 24 hours after the gate
  opened.
- A failed guard gives `approval guard failed`, with no approver entries.
- An approved leg that failed for any other reason stays `approved`. The
  reason is `approval job failure` or `approval job cancelled`. The record
  does not guess why.

`simulated_stages` lists stages that are placeholders. See the
[README](../README.md#simulated-stages).

After a re-run, the record shows the approvals the GitHub API returns, which
may include approvals from earlier attempts of the same run.

### Troubleshooting

The text in angle brackets varies.

| Message | Where | Fix |
| --- | --- | --- |
| `governance.approvers must list at least one approver group` | Check | Add at least one group to `governance.approvers`. |
| `approver group '<name>' cannot be used in a GitHub environment name (letters, digits, '.', '_' and '-'; at most 235 characters)` | Check | Rename the group. |
| `approver group '<name>' is listed more than once (names are case-insensitive)` | Check | Remove the duplicate. |
| `governance.approvers – must be a list of at least one approver group (CHK-05)` | Settings Check tool | Make it a non-empty list of text values. |
| `governance.approvers – must include service.owner_team ('<team>') (CHK-05)` | Settings Check tool | Add the owner team to `governance.approvers`. |
| `deploy.production.approval_mode – is required (CHK-09)` | Settings Check tool | Set `deploy.production.approval_mode`. |
| `deploy.production.approval_mode – must be one of all-approvers, single-approver, unattended (CHK-09)` | Settings Check tool | Use one of the three modes. |
| `deploy.production.exception_id – is required when approval_mode is unattended (CHK-10)` | Settings Check tool | Add the approved exception ID. |
| `Cannot verify the approval environments: the token cannot read the repository's environment settings (HTTP <code>). Grant 'actions: read' to the caller workflow, and create each approval environment in the repository settings with required reviewers (and 'Prevent self-review' enabled).` | Approval guard | Add `actions: read` to the caller's `permissions`, and check that the environments exist. |
| `Cannot verify the approval environments: could not read environment settings after 3 attempts (<reason>)` | Approval guard | Re-run the run. If it keeps failing, check GitHub status. |
| `environment '<name>' does not exist. Create it with required reviewers.` | Approval guard | Create the environment with that name. |
| `environment '<name>' has no required reviewers.` | Approval guard | Add the group's GitHub team as a required reviewer. |
| `environment '<name>' does not prevent self-review. Enable 'Prevent self-review'.` | Approval guard | Select Prevent self-review on the environment. |
| `environment '<name>' lets administrators bypass its protection rules.` | Approval guard (warning) | Optional. Clear the administrator bypass option on the environment. |
| `<environment> was approved more than 24 hours after the gate opened (<time>). Start a new run, or use 'Re-run all jobs'. 'Re-run failed jobs' reuses the original gate time and expires again.` (title "Approval expired") | Approval check | Start a new run, or use "Re-run all jobs". Do not use "Re-run failed jobs". |
| `Invalid gate open time '<value>'; failing closed.` | Approval check | Start a new run. If it repeats, report it to the platform team. |
| `Approval details are unavailable (<reason>). Grant 'actions: read' to the caller workflow.` | Report (warning) | Add `actions: read` to the caller. The run record shows `approvals_unavailable: true` until you do. |

For local development and limitations of the sample pipeline, see
[local development](local-development.md).
