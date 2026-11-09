# Architecture diagrams

The `.drawio` files are the source. The `.png` files are exports, kept so GitHub
shows something when you browse this folder, and so Confluence has an image to
embed.

Change a diagram by editing the `.drawio` file, re-exporting the `.png` and
raising both in the same pull request. A change to the pipeline that makes a
diagram wrong should be caught here, next to the code that broke it.

| File | Shows | Published to |
| --- | --- | --- |
| `1.context.drawio` | Who uses the pipeline, what it connects to and what it produces. C4 Level 1. | Reference Architecture, section 1 |
| `2.pipeline_overview.drawio` | The pieces that make up the standard and how a service connects to them. | Reference Architecture, section 1 |

Confluence holds the published image. This folder holds the source. If the two
disagree, this folder is right.

## Editing

Open a `.drawio` file at [app.diagrams.net](https://app.diagrams.net) or with
the VS Code Draw.io Integration extension. Export with **File, Export as, PNG**
at 200% zoom, no transparent background.