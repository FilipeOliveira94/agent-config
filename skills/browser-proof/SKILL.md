---
name: browser-proof
description: "Proves a change that a person sees or does in a browser: turns the acceptance into statements, drives the running app, and records passed, failed or untested for each one, with screenshots and the exact commit. Use in issue-cycle's verify step when an issue changes a page, a screen, a form, navigation or layout (aconta web, pedsletter, the open-data-platform site, dra-victoria-laufer, filipeoliveira-hub). Not for docs-only, API-only or pipeline-only changes; those record the command and its output."
---

# Browser proof

A green test suite says the code does what the tests ask. It does not say the page works for the person who opens it. This skill is issue-cycle's "look at that surface" for web work. It never replaces the project's checks: run them too.

## 1. Statements before the browser

Before opening the page, turn each acceptance criterion into statements a person could check on screen:

- `Precondition: signed in as the fixture user`
- `It should show the saved value after a reload`

One statement per state change a person would notice, not one per label. Add the viewports and locales that matter: 390 px and 1440 px wide by default, and `pt-BR` and `en` where the UI has both (aconta).

For a bug fix, reproduce the failure on the code before your change (the base branch, or your change stashed) and capture it first. If it does not reproduce, say so: the fix then has no "before".

## 2. Make sure the page is your code

Parallel threads and worktrees share this machine, so the server on a port may be serving another branch.

- Start the project's own dev or preview command from this checkout.
- Confirm the listener: `ss -ltnp "sport = :<port>"`, then `ps -p <pid> -o args=` shows this checkout's path.
- Record `git rev-parse --short HEAD`, the branch and the URL.

## 3. Drive it

Use the first one available:

1. In a T3 thread, the T3 preview tools (load them with ToolSearch): `preview_open`, `preview_act`, `preview_snapshot`, `preview_resize`, and a screenshot of each state.
2. The project's own browser tooling, when it has some (a Playwright config, a puppeteer or axe script). Use it the way the project does.
3. The `playwright` CLI installed for the user (`~/.local/bin/playwright`), with a throwaway script kept outside the repo.

Never add Playwright or another browser dependency to a project for this. Look at the screen before marking a statement: `passed` means you saw it.

## 4. Checks the statements usually miss

On each changed page:

- the browser console shows no new errors;
- no failed requests (4xx, 5xx, blocked assets), and on a site with a privacy promise, no new third-party requests;
- the layout holds at 390 px: nothing clipped, overlapping or scrolling sideways;
- Portuguese text keeps its accents and fits its box;
- when the change touches a form or a dialog, the main path works with the keyboard alone (Tab, Enter, Esc).

## 5. Write it down

Keep the evidence outside the repository, so no project needs a `.gitignore` change: `~/evidence/<repo>/<issue-id>/`.

- Numbered screenshots named after the statement and its result: `01-precondition-signed-in.png`, `02-saves-on-reload-passed.png`.
- `assertions.md`: commit, branch, URL, viewport and locale, then one line per statement with `passed`, `failed` or `untested` and the reason. A statement you could not run is `untested` with the reason, never left out.
- Any throwaway script you used, so the run can be repeated.

## 6. Into the PR

Paste the statement table from `assertions.md` into the PR's checks section as text, with the evidence folder path. Do not upload screenshots or video anywhere: local files never go to external hosts. Filipe can attach media by hand. `po-reviewer` can cite the table as proof that a UI behavior was exercised.

## Guardrails

- No secrets, tokens, real financial data or personal data on screen. Use fixtures (aconta) or a test account. If a flow needs real data, mark it `untested` and say why.
- A screenshot shows the live page you drove in this run. Never present a mock, a static render or an old capture as this run.
- One capture per meaningful state is enough. The goal is a reviewer who believes the behavior, not a gallery.
