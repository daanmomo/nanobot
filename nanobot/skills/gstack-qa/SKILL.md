---
name: gstack-qa
description: "Systematic QA testing for web apps. Four modes: diff-aware (auto on feature branches), full, quick (30s smoke test), regression (compare against baseline). Produces structured report with health score."
metadata: {"nanobot":{"emoji":"🧪","requires":{"bins":["bun"]},"always":false}}
---

# /qa: Systematic QA Testing

You are a QA engineer. Test web applications like a real user — click everything, fill every form, check every state. Produce a structured report with evidence.

## Setup

**Parse the user's request for these parameters:**

| Parameter | Default | Override example |
|-----------|---------|-----------------|
| Target URL | (auto-detect or required) | `https://myapp.com`, `http://localhost:3000` |
| Mode | full | `--quick`, `--regression .gstack/qa-reports/baseline.json` |
| Output dir | `.gstack/qa-reports/` | `Output to /tmp/qa` |
| Scope | Full app (or diff-scoped) | `Focus on the billing page` |
| Auth | None | `Sign in to user@example.com`, `Import cookies from cookies.json` |

**If no URL is given and you're on a feature branch:** Automatically enter **diff-aware mode** (see Modes below).

**Find the browse binary:**

```bash
B=~/.claude/skills/gstack/browse/dist/browse
if [ -x "$B" ]; then
  echo "READY: $B"
else
  echo "NEEDS_SETUP"
fi
```

If `NEEDS_SETUP`:
1. Tell the user: "gstack browse needs a one-time build (~10 seconds). OK to proceed?" Then STOP and wait.
2. Run: `cd ~/.claude/skills/gstack/browse && ./setup`
3. If `bun` is not installed: `curl -fsSL https://bun.sh/install | bash`

**Create output directories:**

```bash
REPORT_DIR=".gstack/qa-reports"
mkdir -p "$REPORT_DIR/screenshots"
```

---

## Modes

### Diff-aware (automatic when on a feature branch with no URL)

This is the **primary mode** for developers verifying their work. When the user says `/qa` without a URL and the repo is on a feature branch, automatically:

1. **Analyze the branch diff** to understand what changed:
   ```bash
   git diff main...HEAD --name-only
   git log main..HEAD --oneline
   ```

2. **Identify affected pages/routes** from the changed files:
   - Controller/route files -> which URL paths they serve
   - View/template/component files -> which pages render them
   - Model/service files -> which pages use those models
   - CSS/style files -> which pages include those stylesheets
   - API endpoints -> test them directly with `$B js "await fetch('/api/...')"`

3. **Detect the running app** — check common local dev ports:
   ```bash
   $B goto http://localhost:3000 2>/dev/null && echo "Found app on :3000" || \
   $B goto http://localhost:4000 2>/dev/null && echo "Found app on :4000" || \
   $B goto http://localhost:8080 2>/dev/null && echo "Found app on :8080"
   ```

4. **Test each affected page/route:**
   - Navigate to the page
   - Take a screenshot
   - Check console for errors
   - If the change was interactive, test the interaction end-to-end
   - Use `snapshot -D` before and after actions to verify the change

5. **Cross-reference with commit messages and PR description** to understand *intent*.

6. **Report findings** scoped to the branch changes.

### Full (default when URL is provided)
Systematic exploration. Visit every reachable page. Document 5-10 well-evidenced issues. Produce health score.

### Quick (`--quick`)
30-second smoke test. Visit homepage + top 5 navigation targets. Check: page loads? Console errors? Broken links?

### Regression (`--regression <baseline>`)
Run full mode, then load `baseline.json` from a previous run. Diff: which issues are fixed? Which are new?

---

## Workflow

### Phase 1: Initialize
1. Find browse binary (see Setup above)
2. Create output directories
3. Start timer for duration tracking

### Phase 2: Authenticate (if needed)

```bash
$B goto <login-url>
$B snapshot -i                    # find the login form
$B fill @e3 "user@example.com"
$B fill @e4 "[REDACTED]"         # NEVER include real passwords in report
$B click @e5                      # submit
$B snapshot -D                    # verify login succeeded
```

Or with a cookie file:
```bash
$B cookie-import cookies.json
$B goto <target-url>
```

### Phase 3: Orient

```bash
$B goto <target-url>
$B snapshot -i -a -o "$REPORT_DIR/screenshots/initial.png"
$B links                          # map navigation structure
$B console --errors               # any errors on landing?
```

### Phase 4: Explore

Visit pages systematically. At each page:

```bash
$B goto <page-url>
$B snapshot -i -a -o "$REPORT_DIR/screenshots/page-name.png"
$B console --errors
```

Per-page checklist:
1. **Visual scan** — Look at the annotated screenshot for layout issues
2. **Interactive elements** — Click buttons, links, controls
3. **Forms** — Fill and submit. Test empty, invalid, edge cases
4. **Navigation** — Check all paths in and out
5. **States** — Empty state, loading, error, overflow
6. **Console** — Any new JS errors after interactions?
7. **Responsiveness** — Check mobile viewport if relevant

### Phase 5: Document

Document each issue **immediately when found**:

**Interactive bugs:**
```bash
$B screenshot "$REPORT_DIR/screenshots/issue-001-step-1.png"
$B click @e5
$B screenshot "$REPORT_DIR/screenshots/issue-001-result.png"
$B snapshot -D
```

**Static bugs:**
```bash
$B snapshot -i -a -o "$REPORT_DIR/screenshots/issue-002.png"
```

### Phase 6: Wrap Up

1. Compute health score (weighted average of category scores)
2. Write "Top 3 Things to Fix"
3. Write console health summary
4. Save baseline JSON for regression mode

---

## Health Score Rubric

### Weights
| Category | Weight |
|----------|--------|
| Console | 15% |
| Links | 10% |
| Visual | 10% |
| Functional | 20% |
| UX | 15% |
| Performance | 10% |
| Content | 5% |
| Accessibility | 15% |

### Scoring
- Console: 0 errors=100, 1-3=70, 4-10=40, 10+=10
- Links: 100, each broken -15 (min 0)
- Other categories: start at 100, deduct per finding (Critical=-25, High=-15, Medium=-8, Low=-3)

---

## Important Rules

1. **Repro is everything.** Every issue needs at least one screenshot.
2. **Verify before documenting.** Retry once to confirm reproducibility.
3. **Never include credentials.** Write `[REDACTED]` for passwords.
4. **Write incrementally.** Append each issue as you find it.
5. **Never read source code.** Test as a user.
6. **Check console after every interaction.**
7. **Test like a user.** Use realistic data.
8. **Depth over breadth.** 5-10 well-documented issues > 20 vague descriptions.
9. **Use `snapshot -C` for tricky UIs.** Finds clickable divs the accessibility tree misses.
