---
name: linkedin-platform-post
description: >-
  Draft spoken Brazilian Portuguese LinkedIn posts about data engineering
  work: portfolio projects, career projects, pipelines, and lessons. Use when
  the user asks for a LinkedIn post, a project update, a portfolio or career
  write-up, a poster or card, or a Portuguese and English version. Read the
  project before writing claims. Draw a new SVG from flexible layout rules
  when the post needs an image; shipped SVGs are examples, not the only layout.
---

# LinkedIn data post

Personal skill for data-engineering posts: a portfolio project, a career project, a pipeline, or a lesson from one. It lives in the home skills directory. Cursor loads it from `~/.cursor/skills/linkedin-platform-post/`. Claude Code loads the same directory through `~/.claude/skills/linkedin-platform-post/`.

Write new SVG templates in that directory's `templates/` folder. Write PNGs to `/tmp` unless the user names another path. Do not commit generated images into a project repo.

## When to run

The user wants a LinkedIn post about data work, a refresh of one, or the image that goes with it.

## Shape

Name the post in one line: what the reader should leave knowing. Then use one shape.

- **Question.** Opens on a question a practitioner actually asks. Fits a pipeline, a check, or a number on a dashboard.
- **What I built.** Portfolio piece. The problem, what you did, what changed, where to look.
- **What I learned.** Career note. One decision, one tradeoff, one thing you would repeat. Not generic advice.
- **How it fits.** Short architecture story. Use this when the post needs a picture.

The audience is another data person who will read, and a recruiter who will skim. Lead with the problem or the decision. The stack is evidence, and it comes after the idea. Do not turn the post into a job application unless the user asks.

## Facts, then copy

Read the project the user pointed at. If they named none, use only what they said in the chat, or ask which project. Do not invent a repo, a metric, a source, a tool, or a date.

When the repo has them, read the overview, any status or roadmap file, and the note for each layer, job, or model the post names.

Three kinds of claim:

- **Done.** Behavior the code, the docs, or the user confirmed.
- **Next.** Only what a roadmap or the user already called out. Do not date it unless they did.
- **Example.** A number that illustrates the idea and was not measured for this post. Say that it is an example.

If docs and an older post disagree, follow the docs. Keep a source the user named. Do not add one they did not.

## Voice

Portuguese first. Plain spoken Brazilian Portuguese, the way you would explain the work to another engineer. Short sentences. One idea each. The first line is a question, a concrete scene, or the result.

`a gente`, `pra`, `tá`, and `dá uma olhada` are fine when the sentence wants them. Do not force slang into every line. Stay in `você`. Do not switch to `tu` unless the user writes that way.

Tool names land after the idea is clear, tied to what they did. Skip the status-report shape, the slogan stack, and the opening that sounds translated: "é com grande alegria", "no mundo dos dados", "vamos mergulhar", "alavancar", "jornada" as filler.

Read it aloud. If you would not say it to a colleague, rewrite it.

English only after the user accepts the Portuguese, unless they already asked for both. Separate the two posts with a line that is exactly `-----------`. The English post keeps the same claims and the same spoken pace.

Close with a link only when one exists: repo, write-up, demo, dashboard. Do not invent a URL.

Hashtags once, after the last post. For data work, start with `#DataEngineering #EngenhariaDeDados`, then add two to four tags the post actually earned. Drop the rest.

### Pace

Pace only. Swap in the project in front of you. Do not reuse these lines as facts.

Question:

```
Todo mundo já viu um número num relatório e pensou: como chegaram nisso?

O caminho desse número começa no arquivo que chegou, passa por uma checagem, e só então vira o valor que alguém usa. ...

O código está aqui:
<url that exists>
```

Portfolio:

```
Passei umas semanas num problema chato: o relatório fechava, a base não.

Separei o que chegou do que a gente confia, e o número passou a ter um caminho. ...

O projeto está aqui:
<url that exists>
```

Career:

```
A parte mais difícil desse projeto não foi a ferramenta.

Foi decidir o que fica cru e o que vira número de negócio. ...
```

## Poster

Draw a poster when the user wants an image, or when the shape is **How it fits**. Skip it for a short career note.

Draw a new SVG. Do not send the poster through an image generator. Text on the image is English unless the user asks for Portuguese on the card.

`templates/trace-report-number.svg` is one worked example: a question, sources, storage, processing, a result, and a next band, for one lakehouse story. Its labels belong to that story. It is not the layout. Change layout, palette, canvas size, and which blocks appear. Reuse that file only when the user wants that poster updated, or as a structural reference while drawing a new one.

Save new SVGs as `templates/<short-name>.svg`. Leave older templates in place.

### Design rules

- The headline matches the post's first line in tone. A question if the post opens with one. A short claim if the post is a build or a lesson.
- Each block looks different. Do not repeat the same card.
- Section titles stay readable. No faint gray on a similar background. A card on a tinted shape needs a fill that still contrasts.
- **Done** and **Next** are visually separate when both appear. Omit **Next** when the story has no next step.
- Default canvas is 1920 wide. Body text is at least 16px at that width, and scales with the width. Nothing clips. Check by rendering, then reading the PNG.
- Font: `Ubuntu Sans`, fallback `DejaVu Sans`.
- One ink, one accent, enough contrast to read on a phone. Palette can change.
- Shadows and a few large color shapes are welcome. No circuit boards, hex grids, or stock "AI" glow.

### Blocks

Use the blocks the story needs. Skip the rest.

- **Sources.** Only sources the post names.
- **Landing.** What is kept as it arrived, plus the detail that matters: date, origin, key.
- **Processing.** Who transforms what, in the order the project uses. Name a tool only when the post does.
- **Result.** The question the data answers, or the thing a recruiter should remember. An example number is labeled `EXAMPLE FIGURE`. A measured number is labeled as measured.
- **Next.** Only items the user or the roadmap already named.
- **Lesson.** For a career post: problem, decision, outcome. Two or three beats. No pipeline required.

## Render

From any directory, using the skill directory you loaded:

```bash
"$SKILL_DIR/scripts/render_svg.sh" \
  "$SKILL_DIR/templates/<name>.svg" \
  /tmp/<name>.png
```

The script refuses a PNG inside a git checkout. If the user asked for that path, rerun with `ALLOW_IN_REPO=1`. Give the user the PNG path.

After render, read the PNG and fix clipped or overlapping text before showing it.

## Before you send

- The first line can be said out loud.
- Every **Done** claim was checked. Every **Next** item was already named. Every illustrative number is marked as an example.
- Tool names explain a step. They are not the opening.
- The link exists. The hashtags match this post.
- If there is a poster, the blocks match the post, and the PNG was read back.
