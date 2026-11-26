---
name: module-boundaries
description: "Decides where shared logic lives: whether to extract code that repeats across flows, and which module, service or layer owns a new behavior. Use when the same operation appears in two or more places, when a fix in one path should reach the others, or when issue-cycle's implement step has to choose a boundary. The project's AGENTS.md architecture always wins."
---

# Module boundaries

A short check before you extract repeated logic or decide where new code goes. It is not an architecture. The repository's `AGENTS.md` describes the real layout (aconta's ledger, `reporting/` and services; open-data-platform's ingestion sources, Spark jobs and statement builders; pedsletter's architecture section). Where it says something, it wins over this file.

## 1. Name the owners

Before writing a function, name who already owns:

- the policy: the rule that decides whether and when something happens;
- the persistence: the module that reads and writes that data;
- the transaction: where it starts and where it commits.

New code goes next to those owners. If the issue needs a new owner, say so in the plan.

## 2. Find every copy

List each place that performs the same operation before changing any of them. In a repo with `.codegraph/`, ask `codegraph_explore` ("who calls X", "where is Y done"); otherwise use Grep. A fix that reaches one copy and misses another is the bug this skill exists to prevent.

## 3. Decide whether to extract

Extract when:

- the same mechanic runs in two or more places, or
- one caller already needs a boundary now: a test seam, a provider or SDK behind one interface, a transaction, logic too dense to read inline.

Do not extract:

- a wrapper with one caller and no seam;
- a layer for a future caller nobody has named;
- a "do everything" function that hides the flow behind flags.

The split: what the flow means stays with the caller (business rules, state transitions, auth and ownership checks, user-facing errors, retries). How to perform one operation reliably moves to the shared module (the provider call, the command, the file format, the readiness check).

## 4. Shape of the shared function

- Every input is a parameter. No hidden globals, no config read deep inside.
- It returns a result the caller can branch on (a typed value, a dataclass, named fields), or raises a documented exception. Failure is never silent.
- Writes and side effects show in the name or the signature. The transaction stays where the project's architecture puts it.
- Functions in one module take arguments and report errors the same way.

The shape, not real code:

```python
# shared module: the mechanic, explicit inputs, a result the caller can branch on
def fetch_snapshot(url: str, *, timeout_s: float, session: Session) -> Snapshot: ...

# caller: the flow decides when to fetch and what "too old" means
snap = fetch_snapshot(SOURCE_URL, timeout_s=30, session=session)
if snap.age_days > 7:
    raise StaleSourceError(source="ibge", fetched_at=snap.fetched_at)
```

## 5. Move one caller at a time

1. Extract the operation and switch one caller to it.
2. Run that project's checks.
3. Switch the remaining callers, then run the checks again.
4. Auth, status transitions, error handling and transaction behavior stay the same for every caller. A behavior change is a separate issue.

If the extraction would touch callers outside the issue's scope, stop and propose it as its own issue. issue-cycle asks for the smallest change that makes the acceptance true.

## 6. Put it in the plan

Add one line to the plan: `Boundaries: policy in <X>, persistence in <Y>, transaction in <Z>; extracting <operation> because <reason>.` The reviewers check the change against that line.
