---
name: linkedin-platform-post
description: >-
  Draft a LinkedIn post and an English architecture poster for the open data
  platform. Use when the user asks for a LinkedIn post, a project update for
  LinkedIn, a poster or card about the platform, or a Portuguese and English
  version of that post. Reads verified status before writing claims. Draws a
  new SVG from the design rules; shipped SVGs are templates, not the only layout.
---

# LinkedIn platform post

Personal skill. It lives in the home directory, never in the open-data-platform repo. Do not add this skill, its templates, or generated PNG/SVG files to that git tree.

Cursor loads it from `~/.cursor/skills/linkedin-platform-post/`. Claude Code loads the same directory through `~/.claude/skills/linkedin-platform-post/`. Write new templates next to the SVG you read, in that directory's `templates/` folder.

## When to run

The user wants a LinkedIn post about this platform, a refresh of the last one, or the image that goes with it.

## Facts, then copy

Read, in the repo if it is the workspace:

1. `PROJECT_STATUS.md` — what is verified
2. `ROADMAP.md` — what is still ahead
3. The architecture note for any layer the post names (Bronze write mode is in `docs/architecture/bronze-layer.md`)

Split the story in two:

- **In place:** only verified behavior.
- **Still ahead:** roadmap items not verified yet. Say they come next. Do not date them as "the next few weeks" unless the user does.

Re-check claims that drift:

- Bronze write mode is whatever the Bronze doc says now. Do not call it append-only while the doc says full overwrite. Raw files are what stay, with date and origin.
- A figure on the poster is an example. Label it `EXAMPLE FIGURE`. Do not print a live metric as if the poster measured it.
- Name sources the user wants highlighted. Do not invent sources. Do not drop a source the user named.

## Voice

Portuguese first. Plain spoken Brazilian Portuguese. Question in the first line. Tool names only after the idea is clear. Not a status report, not a slogan stack.

English only after the user accepts the Portuguese, unless they already asked for both. Separate the two posts with a line that is exactly `-----------`.

Close with the repo URL:

`https://github.com/FilipeOliveira94/open-data-platform`

Hashtags once, after the last post:

`#DataEngineering #EngenhariaDeDados #OpenSource #DataPlatform #Lakehouse #DataQuality #AnalyticsEngineering #ApacheSpark #dbt #ApacheIceberg`

Match this pace. Do not reuse the paragraph as current facts; refresh the facts.

```
Todo mundo já viu um número num relatório e pensou: como chegaram nisso?

Estou montando uma plataforma de dados open source para esse número ter um caminho confiável, da origem até quem usa. ...

Se tiver interesse, dá uma olhada no meu repo:
https://github.com/FilipeOliveira94/open-data-platform
```

The English post asks the same question (`how did they get that?`) and keeps the same claims.

## Poster

Draw a new SVG. Do not send the poster through an image generator. Text on the image is English.

`templates/trace-report-number.svg` is **one template among many**. It shows a layout that already worked: a questioning title, sources, storage, processing, results, and a still-ahead band. Generate other posters from the rules below. Change layout, palette, canvas size, and composition when the story or the user asks for a different image. Reuse that file only when the user wants that poster updated, or as a structural reference while drawing a new one.

Save new SVGs beside it, with a new filename (`templates/<short-name>.svg`). Leave older templates in place.

### Design rules (every poster)

- Headline is a question, same tone as the post's first line.
- Each role looks different. Sources, storage, processing, results, and still-ahead are not the same card repeated.
- Section titles stay readable. No faint gray labels on a similar background.
- A card that sits on a tinted blob needs a fill that still contrasts. Check the Olist-style source chip against the background behind it.
- In-place work and still-ahead work are visually separate.
- Body text is at least 16px on a 1920-wide canvas. Nothing clips. Check by rendering, then reading the PNG.
- Font: `Ubuntu Sans`, fallback `DejaVu Sans`.
- Palette can change. Keep one ink color, one accent, and enough contrast to read on a phone.
- Shadows and a few large color shapes are welcome. No circuit boards, hex grids, or stock "AI" glow.

### What the picture has to say

Even when the layout changes, the picture still answers: where a report number comes from.

- Sources the post names.
- Storage keeps the original file, with date and origin. Bad rows stay visible.
- Processing shows who writes and who builds the business layer, as the docs describe it now (Spark writes Bronze and Silver; Trino and dbt build Gold; Iceberg is the shared table format, until a decision changes that).
- Results show business questions the marts answer, plus one example number labeled `EXAMPLE FIGURE`.
- Still ahead lists roadmap items, not wishes.

## Render

From any directory, using the skill directory you loaded (`~/.cursor/skills/linkedin-platform-post` or `~/.claude/skills/linkedin-platform-post`):

```bash
"$SKILL_DIR/scripts/render_svg.sh" \
  "$SKILL_DIR/templates/<name>.svg" \
  /tmp/<name>.png
```

The script refuses paths inside `open-data-platform`. Give the user the PNG path. Do not commit it.

After render, read the PNG and fix clipped or overlapping text before showing it.
