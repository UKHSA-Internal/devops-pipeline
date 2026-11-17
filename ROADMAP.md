# Roadmap

What the shared pipeline does today, what is being worked on, and what later versions could carry.

Nothing on this page is a commitment or a date. This work runs until March 2027, and whoever maintains the pipeline after that decides what happens to anything listed under Under Consideration.

Last reviewed November 2026. The pipeline is changing quickly at the moment, so parts of this page go out of date between releases. Check the release notes and tags for what is actually published.

## How to Read This Page

Four sections, in order of certainty.

- **What the Pipeline Does Today** is what a service gets right now
- **Planned** is intended before March 2027. Some of it is being built and some has not started
- **Under Consideration** is not committed, not scheduled and not assigned
- **Not Planned** is what was considered and ruled out, with the reason

Anything that would require a service to change something on its side arrives as a new major version, so a service pinned to a major tag is not affected until it chooses to move. Everything else reaches a service without it doing anything.

## What the Pipeline Does Today

A service declares itself in a settings file, gets the steps run in a fixed order, and gets a run record out of it.

| Step | What It Does Today |
|---|---|
| Check | Runs the standards check against the service's settings file |
| Test | Sets up the runtime the service declares, then runs the service's own test command |
| Scan | Simulated. No scanning tool runs |
| Build | Builds and saves a container image. It is not published to a registry |
| Deploy | Not implemented. The shared pipeline carries no cloud deployment code |
| Verify | Calls the service's health endpoint after a deployment. With Deploy not implemented there is nothing real to check |

So a service adopting today gets the step order, the settings file, the standards check and the run record. It does not get scanning, a published image or a deployment.

## Planned

Intended before March 2027. Nothing here has a date, and some of it has not started. The releases and tags are the only record of what has actually shipped.

| Item | What It Changes for a Service |
|---|---|
| Deployment to AWS | Deploy stops being a stub. A service deploys to its own accounts through the shared pipeline |
| Scanning tools in the Scan step | Scan runs real tools instead of a simulation. Which tools, and what stops a release, is being agreed with the agency's security function |
| Production approval gate | A deployment to production waits for a named approver group to sign off |
| Secrets after authentication | A service reaches the secrets it needs once the pipeline has authenticated to its cloud account |
| AI-assisted code review | A pull request carries review comments from a tool. Inform only, it blocks nothing |

## Under Consideration

Not committed, not scheduled, not assigned.

| Item | What It Would Change for a Service |
|---|---|
| Azure support | A service hosted on Azure can adopt the standard. The pipeline targets AWS only today |
| The standards check reads the repository | The check reports on what a repository holds, not only on what its settings file declares. A service sees whether it has a health endpoint and a container definition before it tries to onboard |
| Dependency caching | A service keeps the caching it has today. The shared pipeline caches nothing, so a service that caches dependency installs loses that when it adopts |
| Application dependencies in the run record | The run record carries application dependencies the way it already carries them for infrastructure code |
| Ephemeral environments per branch | A branch gets its own short-lived environment and gives it back when it is merged or closed |
| A record of which services are on the standard | Adoption can be measured, and a scheduled standards check has a list of services to run against. Nothing records this today |

## Not Planned

Considered and ruled out. Listed with the reason so the same question does not come back.

- **Diagram source as code.** Diagrams are kept in a format on the agency's approved tooling list. The text-based alternatives are not on that list.
- **The standards check blocking a merge.** The check reports and never blocks. A rule that has to stop a change belongs in the pipeline itself, where the outcome appears in the run record.
- **The pipeline owning performance baselines and trend tracking.** A service can already run a performance check through its test command. Owning baselines and trends is a separate piece of work, and the test pack and thresholds sit with the agency's central testing function.
- **On-premises hosting.** Out of scope for this phase of the work.
- **Measuring how long an approval takes.** The pipeline does not record it, so the figure would be estimated rather than measured.

## Keeping This Page Current

An item moves out of Under Consideration when someone picks it up. It moves to Not Planned when a decision is taken against it, with the reason written in.

If something here is wrong, out of date or missing, raise an issue against this repository.