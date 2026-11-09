# Architecture Diagrams

Each `.drawio.png` is both the image and the source. GitHub renders it, Confluence
embeds it, and draw.io opens it as an editable diagram. There is no second file to
keep in step.

| File | Shows | Published To |
| --- | --- | --- |
| `1.context.drawio.png` | Who uses the pipeline, what it connects to and what it produces. C4 Level 1. | Reference Architecture, section 1 |
| `2.pipeline_overview.drawio.png` | The pieces that make up the standard and how a service connects to them. | Reference Architecture, section 1 |
| `3.pipeline_components.drawio.png` | What runs inside the shared pipeline workflow, in what order, and what each part reads or writes. C4 Level 3. | Low Level Design, section 2.1 |

Confluence holds the published image. This folder holds the source. If the two
disagree, this folder is right.

## Editing

Use the VS Code Draw.io Integration extension or the draw.io desktop app. Both read
the diagram out of the PNG and both run locally.

Save the file, do not export it. Saving keeps the source embedded. Exporting to PNG
drops it unless **Include a copy of my diagram** is ticked, and nothing warns you.
Open the file again before raising a pull request and check it still comes up as an
editable diagram.

## Publishing to Confluence

Upload the same `.drawio.png` as an image attachment. No export, no second file.

Do not import it into the draw.io Confluence macro. That creates a second editable
copy which drifts from this one.