---
name: plain-voice
description: "Second pass over prose a person will read, once the draft exists: removes AI tells and makes it sound like Filipe. Use on LinkedIn posts and other published text (after linkedin-platform-post writes the draft), on PR titles and descriptions, READMEs and docs, and whenever the user asks to make text sound natural or less like AI. Not for each commit message, and never on compliance-checked site copy."
---

# Plain voice

Adapted from unslop by Lauren Tan (MIT, see `LICENSE`). This is an edit pass over a draft that already exists. It does not decide facts, structure or shape: `linkedin-platform-post` owns those for posts, `issue-cycle` for PRs.

## Pick the register

| Register | Used for | Goal |
|---|---|---|
| Spoken | LinkedIn posts, public prose, replies | Sounds like Filipe explaining the work to another engineer, out loud |
| Engineering | PR titles and bodies, READMEs, docs, code comments | Dry and specific: what changed, why, what was run |

The engineering register removes tells and applies the plain-speech rules. It adds no opinions, reactions or first-person color. Conventional commit prefixes stay.

Do not run it on commit messages one by one, on text the user wrote and did not ask to edit, or on dra-victoria-laufer site copy and any wording checked against a compliance list (the CFM checklist): there, a "more natural" word can break a rule.

## Process

1. Read `voice/samples.md` and `voice/edits.md` when they have entries. They beat every rule below: when a sample does something a rule forbids, follow the sample.
2. Scan the draft for the patterns below.
3. Rewrite. Keep every fact, number, link and claim exactly. Change words and rhythm only.
4. Spoken register: read it aloud. Would Filipe say this to a colleague? Rewrite any line where the answer is no.
5. Ask what in the text still says "a model wrote this", and fix it.
6. Report in a few lines what changed: the patterns removed and any line you were unsure about. When the user vetoes a change or rewrites a line, add the pair to `voice/edits.md`.

## Sounding natural (spoken register)

Removing tells gives clean text. Natural is a different thing.

- Uneven rhythm. A short line. Then a longer one that takes its time. Neither every sentence the same length nor a string of fragments.
- One concrete detail beats an adjective: the file that arrived late, the number that did not match.
- A lesson can take a side: what you would do again, what you would skip. A build post states what changed, with no forced opinion.
- First person is fine.
- Leave a little mess: one aside, a question you actually had. Perfect symmetry reads as generated.
- Do not overcorrect into a chain of tiny sentences. That is its own tell.

## Portuguese (pt-BR)

Posts are Portuguese first, and the English word lists below do not translate. This section is the one home for the Portuguese word rules; `linkedin-platform-post` points here.

Cut:

- Translated openings and filler: "é com grande alegria", "no mundo dos dados", "no cenário atual", "vamos mergulhar", "neste post", "vale ressaltar", "é importante destacar", "em suma".
- Buzzwords as filler: "alavancar", "potencializar", "jornada", "robusto", "disruptivo", "virar a chave".
- "Não é apenas X, é Y" and "não só X, mas também Y". Say the point.
- Hook chains: "O resultado?", "E o melhor?", "Spoiler:".
- Gerundismo: "vou estar enviando" becomes "vou enviar".
- Emojis as bullets (🚀, ✅, 👉) and hashtags in the middle of the text.

Keep:

- `você`. Do not switch to `tu` unless the user writes that way.
- `a gente`, `pra`, `tá`, `dá uma olhada` when the sentence wants them, not in every line.
- Punctuation the way a Brazilian writes it. A rare dash or a real parenthetical is fine in Portuguese; the dash rule below is for English.

## Patterns to remove

### Content

1. **Puffery.** "pivotal moment", "testament to", "evolving landscape", "setting the stage for". State what happened.
2. **Name-dropping.** A list of outlets or companies without context. Pick one and say what it did.
3. **Superficial -ing phrases.** "highlighting...", "ensuring...", "showcasing...", "fostering...". Delete, or say the real effect.
4. **Promotional words.** "vibrant", "breathtaking", "groundbreaking", "stunning". Describe it plainly.
5. **Vague attributions.** "Experts believe", "Industry reports suggest". Name the source or delete.
6. **Formulaic challenges.** "Despite challenges, it continues to thrive." Give the specific fact.

### Language

7. **AI vocabulary.** additionally, crucial, delve, enduring, enhance, fostering, garner, interplay, intricate, landscape, pivotal, showcase, tapestry, testament, underscore, vibrant. Use the plain word.
8. **Fancy "is".** "serves as", "stands as", "boasts". Say "is" or "has".
9. **"Not just X, but Y."** State the point directly.
10. **Rule of three.** Ideas forced into groups of three. Use the real number.
11. **Synonym cycling.** Pick one name for a thing and repeat it.
12. **False ranges.** "from X to Y" where X and Y are not on one scale. List the items.

### Style

13. **Em dashes in English.** Use a period or a comma. A parenthesis is fine for a real aside, not as a dash substitute.
14. **Colon as a connector.** Colons go before a list or an example, not mid-sentence to set up a contrast.
15. **Bold everywhere.** Do not bold every name or acronym.
16. **Inline-header lists.** "**Performance:** Performance improved..." becomes prose. A bold lead-in that names the item and is followed by new detail is fine.
17. **Title Case Headings.** Use sentence case.
18. **Decorative emojis** in headings and bullets.
19. **Curly quotes.** Use straight quotes.

### Chatbot residue

20. "I hope this helps!", "Let me know if...", "Of course!", "Certainly!".
21. Cutoff disclaimers: "While specific details are limited...".
22. Sycophancy: "Great question!", "You're absolutely right!".

### Filler

23. "In order to" becomes "to". "Due to the fact that" becomes "because". "It is important to note that" goes.
24. Stacked hedging: "could potentially possibly" becomes "may".
25. Generic endings: "The future looks bright." End on a fact or the next step.

### Jargon

26. **Abstract metaphor nouns.** substrate, wedge, vector, locus, nexus, primitive, harness, surface (API surface), bedrock, scaffolding, paradigm, gold-plating, ratchet, endgame, north star, flywheel. Use the concrete word: "base", "add", "way", "more than the job needs", "the last phase".

### Plain speech

27. **Say what it does, not how it feels.** "SQL you can read" becomes "`.toSQL()` returns the exact string sent to the database". If a sentence could appear unchanged in another project's docs, it says nothing about this one: cut it.
28. **One idea per sentence.** If the reader has to backtrack, split it or drop a clause.
29. **Active voice.** "Queries are validated" becomes "the compiler validates queries", unless the actor is unknown or does not matter.
30. **Adverbs.** "significantly improves" becomes the measured change. An adverb propping up a verb means the verb is wrong.
31. **Plain words.** utilize, leverage, facilitate, numerous, in the event that: use, use, help, many, if.
