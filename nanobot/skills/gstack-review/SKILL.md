---
name: gstack-review
description: "Pre-landing PR review. Analyzes diff against main for SQL safety, LLM trust boundary violations, conditional side effects, and other structural issues."
metadata: {"nanobot":{"emoji":"👀","requires":{"bins":["git"]},"always":false}}
---

# Pre-Landing PR Review

You are running the `/review` workflow. Analyze the current branch's diff against main for structural issues that tests don't catch.

---

## Step 1: Check branch

1. Run `git branch --show-current` to get the current branch.
2. If on `main`, output: **"Nothing to review — you're on main or have no changes against main."** and stop.
3. Run `git fetch origin main --quiet && git diff origin/main --stat` to check if there's a diff. If no diff, output the same message and stop.

---

## Step 2: Read the checklist

Read `.claude/skills/review/checklist.md` if available. If not found, use the built-in checklist below.

### Built-in Review Checklist

**Pass 1 (CRITICAL):**

1. **SQL & Data Safety**
   - Raw SQL with string interpolation/concatenation (SQL injection risk)
   - Missing transaction blocks around multi-step data mutations
   - Destructive operations (DELETE, DROP, TRUNCATE) without safeguards
   - Mass updates/deletes without WHERE clause or LIMIT

2. **LLM Output Trust Boundary**
   - LLM output used directly in SQL, shell commands, or file paths
   - LLM output rendered as HTML without sanitization (XSS)
   - LLM output used to make authorization decisions

**Pass 2 (INFORMATIONAL):**

3. **Conditional Side Effects** — Side effects (DB writes, API calls, emails) inside conditionals without else-branch handling
4. **Magic Numbers & String Coupling** — Hardcoded values that should be constants; strings that couple distant parts of the codebase
5. **Dead Code & Consistency** — Unreachable code, commented-out blocks, inconsistent naming
6. **Test Gaps** — New public methods/endpoints without corresponding tests
7. **Security** — Secrets in code, overly permissive CORS, missing auth checks

---

## Step 3: Get the diff

Fetch the latest main to avoid false positives from a stale local main:

```bash
git fetch origin main --quiet
```

Run `git diff origin/main` to get the full diff.

---

## Step 4: Two-pass review

Apply the checklist against the diff in two passes:

1. **Pass 1 (CRITICAL):** SQL & Data Safety, LLM Output Trust Boundary
2. **Pass 2 (INFORMATIONAL):** All remaining categories

---

## Step 5: Output findings

**Always output ALL findings** — both critical and informational.

- If CRITICAL issues found: output all findings, then for EACH critical issue ask the user with the problem, your recommended fix, and options (A: Fix it now, B: Acknowledge, C: False positive — skip).
- If only non-critical issues found: output findings. No further action needed.
- If no issues found: output `Pre-Landing Review: No issues found.`

---

## Important Rules

- **Read the FULL diff before commenting.** Do not flag issues already addressed in the diff.
- **Read-only by default.** Only modify files if the user explicitly chooses "Fix it now" on a critical issue.
- **Be terse.** One line problem, one line fix. No preamble.
- **Only flag real problems.** Skip anything that's fine.
