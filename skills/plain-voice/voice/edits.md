# Edit log

Lines from a draft that still felt off, and what Filipe said about them. `plain-voice` reads this before editing. When the same kind of fix shows up twice, turn it into a rule in `SKILL.md` and delete those entries. The 2026-11-25 notes below are already rules there ("Sounding natural").

## Words and phrases

| Filipe says | Filipe never says |
|---|---|
| Ficou na minha cabeça | Vamos pra cima |
| Me fez pensar | Não consigo provar o conceito |
| Me deixou impressionado | Tenho muita experiência como desenvolvedor |
| Criamos algo diferente, porém, efetivo | Ninguém pode me provar o contrário |
| Vamos precisar ajustar isso aí | Isso aqui pra mim é fácil |

## Corrections

<!-- Template

### <date> · <post or PR>

- Draft: "<line as the draft had it>"
- Filipe: "<line as Filipe wants it>", or the problem in Filipe's words
- Why: <a word Filipe would not say, rhythm too even, sounds translated, too polite>

-->

### 2026-11-25 · LinkedIn draft on full overwrite vs incremental (open-data-platform)

The whole draft:

- Why: short sentences without grammatical construction, one per line. And the sentences talk about too many different concepts: full overwrite, row counts, the MERGE placeholder, runtimes, old Parquet files, snapshot expiry, the PostgreSQL window, Airflow schedules, exactly-once, the stack.

Line by line:

- Draft: "Por que o meu pipeline reconstrói a tabela inteira a cada execução, em vez de ser incremental?"
  - Why: the question does not sound natural.
- Draft: "Porque eu ainda não consigo provar o incremental. Então não finjo que ele existe."
  - Why: it does not make sense. What would "provar o incremental" be?
  - Direction: talk about implementing the incremental method, or adopting incremental ingestion.
- Draft: "O custo é real."
  - Why: sounds forced and robotic.
- Draft: "Exactly-once eu não afirmo."
  - Why: forced and robotic, same as above.
- Draft: "E você, começa no full overwrite e só parte pro incremental quando consegue provar, ou já nasce incremental?"
  - Why: the right idea, badly written. It should ask one thing in plain words.
