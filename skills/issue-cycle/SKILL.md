---
name: issue-cycle
description: "Ships one product issue from a plan through a checked outcome. Use when the user names an issue, acceptance criteria, a feature to build, or asks to close or verify an issue."
---

# Issue cycle

One issue at a time. Its acceptance text is the definition of done. Do not pull in later issues, and do not change that text while building.

## Inspect

Read the issue, the acceptance text, and the current product status. Do not change files.

Reply with scope, out of scope, the approach, and what a person can do when it is done. Stop unless they have already asked to build it.

## Build

Make the smallest change that makes the accepted behavior true.

Do not add a confirmation, a restriction, or an extra step the issue did not ask for.

## Check

Exercise each behavior the issue includes, the way a person using the product would. A behavior you did not exercise is not done. Name any you skipped, and why, before calling the issue done.

A passing internal check is not enough when the person would see a different surface. Look at that surface too.

A check you did not run is not a pass. Report what you ran and what happened.

## Record

Write what was built and what the checks showed. Leave out detours that do not change how someone uses the result.

Compare that to the acceptance text. Say what is satisfied and what is still open. Commit only when asked.
