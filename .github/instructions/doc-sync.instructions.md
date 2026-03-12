---
applyTo: "**"
description: "Rules to keep documentation synchronized with code changes"
---

# Rules to keep documentation up-to-date

- Rule 1: Whenever changes are made to the codebase, it's important to also update the documentation to reflect those changes. You must ensure that the following documentation is updated: [Starlight content pages in docs/src/content/docs/](../../docs/src/content/docs/). Each page uses Starlight frontmatter (title, sidebar order). Cross-page links use relative paths (e.g., `../../guides/compilation/`).

- Rule 2: The main [README.md](../../README.md) file is a special case that requires user approval before changes, so, if there is a deviation in the code that affects what is stated in the main [README.md](../../README.md) file, you must warn the user and describe the drift and [README.md](../../README.md) update proposal, and wait for confirmation before updating it. 

- Rule 3: Documentation is meant to be very simple and straightforward, we must avoid bloating it with unnecessary information. It must be pragmatic, to the point, succint and practical.To: "**"