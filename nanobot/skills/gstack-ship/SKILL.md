---
name: gstack-ship
description: "Ship workflow: merge main, run tests, review diff, bump VERSION, update CHANGELOG, commit, push, create PR."
metadata: {"nanobot":{"emoji":"🚀","requires":{"bins":["git","gh"]},"always":false}}
---

# Ship: Fully Automated Ship Workflow

You are running the `/ship` workflow. This is a **non-interactive, fully automated** workflow. Do NOT ask for confirmation at any step. The user said `/ship` which means DO IT. Run straight through and output the PR URL at the end.

**Only stop for:**
- On `main` branch (abort)
- Merge conflicts that can't be auto-resolved (stop, show conflicts)
- Test failures (stop, show failures)
- Pre-landing review finds CRITICAL issues and user chooses to fix
- MINOR or MAJOR version bump needed (ask)

**Never stop for:**
- Uncommitted changes (always include them)
- Version bump choice (auto-pick MICRO or PATCH)
- CHANGELOG content (auto-generate from diff)
- Commit message approval (auto-commit)

---

## Step 1: Pre-flight

1. Check the current branch. If on `main`, **abort**: "You're on main. Ship from a feature branch."
2. Run `git status` (never use `-uall`). Uncommitted changes are always included.
3. Run `git diff main...HEAD --stat` and `git log main..HEAD --oneline` to understand what's being shipped.

---

## Step 2: Merge origin/main (BEFORE tests)

```bash
git fetch origin main && git merge origin/main --no-edit
```

If merge conflicts are complex or ambiguous, **STOP** and show them.

---

## Step 3: Run tests (on merged code)

Run the project's test suite. Common patterns:

```bash
# Python projects
pytest 2>&1 | tee /tmp/ship_tests.txt

# Node projects
npm test 2>&1 | tee /tmp/ship_tests.txt

# Or whatever the project uses
```

If any test fails, show the failures and **STOP**.

---

## Step 4: Pre-Landing Review

1. Run `git diff origin/main` to get the full diff.
2. Apply the review checklist in two passes:
   - **Pass 1 (CRITICAL):** SQL & Data Safety, LLM Output Trust Boundary
   - **Pass 2 (INFORMATIONAL):** All remaining categories
3. If CRITICAL issues found: ask user for each (Fix / Acknowledge / Skip).
4. If only non-critical: output and continue.
5. If none: output `Pre-Landing Review: No issues found.`

---

## Step 5: Version bump (auto-decide)

1. Read the current `VERSION` file (if it exists)
2. Auto-decide the bump level based on diff size:
   - **MICRO/PATCH**: < 50 lines changed, trivial tweaks
   - **PATCH**: 50+ lines changed, bug fixes, small-medium features
   - **MINOR**: **ASK the user** — major features or significant changes
   - **MAJOR**: **ASK the user** — milestones or breaking changes
3. Write the new version to the `VERSION` file.

If no VERSION file exists, skip this step.

---

## Step 6: CHANGELOG (auto-generate)

1. Read `CHANGELOG.md` header to know the format (if it exists).
2. Auto-generate the entry from all commits on the branch.
3. Categorize: Added, Changed, Fixed, Removed.
4. Insert after the file header, dated today.

If no CHANGELOG.md exists, skip this step.

---

## Step 7: Commit (bisectable chunks)

Create small, logical commits:
- Infrastructure first (migrations, config, routes)
- Models & services with their tests
- Controllers & views with their tests
- VERSION + CHANGELOG in the final commit

Each commit message: `<type>: <summary>` (feat/fix/chore/refactor/docs).
Only the final commit gets the co-author trailer:
```
Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## Step 8: Push

```bash
git push -u origin <branch-name>
```

---

## Step 9: Create PR

```bash
gh pr create --title "<type>: <summary>" --body "$(cat <<'EOF'
## Summary
<bullet points from CHANGELOG>

## Pre-Landing Review
<findings from Step 4, or "No issues found.">

## Test plan
- [x] All tests pass

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**Output the PR URL** — this should be the final output the user sees.

---

## Important Rules

- **Never skip tests.** If tests fail, stop.
- **Never force push.** Use regular `git push` only.
- **Never ask for confirmation** except for MINOR/MAJOR version bumps and CRITICAL review findings.
- **The goal is: user says `/ship`, next thing they see is the review + PR URL.**
