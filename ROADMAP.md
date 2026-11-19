# Roadmap

What the shared pipeline does today, what is being worked on and what later versions could carry.

Nothing on this page is a commitment or a date. This work runs until March 2027. Whoever maintains the pipeline after that decides what happens to anything listed under Under Consideration.

Last reviewed November 2026. The pipeline is changing quickly at the moment, so parts of this page go out of date between releases. Check the release notes and tags for what is actually published.

## How to Read This Page

Sections run in order of certainty.

- **What the Pipeline Does Today** is what a service gets right now
- **Planned** is intended before March 2027. Some of it is being built and some has not started
- **Under Consideration** is not committed, not scheduled and not assigned
- **Not Planned** is what was considered and ruled out, with the reason

A service pins to a major version tag and picks up everything released under that tag.

## What the Pipeline Does Today

A service declares itself in a settings file, gets the steps run in a fixed order and gets a run record out of it.

| Step | What It Does Today |
|---|---|
| Check | Runs the standards check against the service's settings file |
| Test | Sets up the runtime the service declares, then runs the service's own test command |
| Scan | Simulated. No scanning tool runs |
| Build | Builds and saves a container image. It is not published to a registry |
| Approve | A production deployment waits for the approver groups named in the settings file. Approvals expire after 24 hours. With Deploy not implemented there is nothing yet to hold back |
| Deploy | Not implemented. The shared pipeline carries no cloud deployment code |
| Verify | Calls the service's health endpoint after a deployment. With Deploy not implemented there is nothing real to check |

So a service adopting today gets the step order, the settings file, the standards check, the approval gate and the run record. It does not get scanning, a published image or a deployment.

## Planned

Intended before March 2027. Nothing here has a date and some of it has not started. The releases and tags are the only record of what has actually shipped.

| Item | What It Changes for a Service |
|---|---|
| Deployment to AWS | Deploy stops being a stub. A service deploys to its own accounts through the shared pipeline |
| Scanning tools in the Scan step | Scan runs real tools instead of a simulation. Which tools run and what stops a release are being agreed with the agency's security function |
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
| A record of which services are on the standard | Adoption can be measured and a scheduled standards check has a list of services to run against. Nothing records this today |

## Not Planned

Considered and ruled out. Listed with the reason so the same question does not come back.

- **Diagram source as code.** The approved tooling list does not carry the text-based alternatives.
- **The pipeline owning performance baselines and trend tracking.** A service can already run a performance check through its test command. The pack and the thresholds sit with the agency's central testing function.
- **On-premises hosting.** Out of scope for this phase of the work.
- **Measuring how long an approval takes.** The pipeline does not record it, so any figure would be an estimate.

## Keeping This Page Current

An item moves out of Under Consideration when someone picks it up. It moves to Not Planned when a decision is taken against it, with the reason written in.

If something here is wrong, out of date or missing, raise an issue against this repository.