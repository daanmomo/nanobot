---
name: gstack-retro
description: "Weekly engineering retrospective. Analyzes commit history, work patterns, and code quality metrics with persistent history and trend tracking. Team-aware with per-person analysis."
metadata: {"nanobot":{"emoji":"📊","requires":{"bins":["git"]},"always":false}}
---

# /retro — Weekly Engineering Retrospective

Generates a comprehensive engineering retrospective analyzing commit history, work patterns, and code quality metrics. Team-aware: identifies the user running the command, then analyzes every contributor with per-person praise and growth opportunities.

## Arguments
- `/retro` — default: last 7 days
- `/retro 24h` — last 24 hours
- `/retro 14d` — last 14 days
- `/retro 30d` — last 30 days
- `/retro compare` — compare current window vs prior same-length window
- `/retro compare 14d` — compare with explicit window

## Instructions

Parse the argument to determine the time window. Default to 7 days if no argument given. All times reported in **Pacific time** (use `TZ=America/Los_Angeles`).

### Step 1: Gather Raw Data

First, fetch origin and identify the current user:
```bash
git fetch origin main --quiet
git config user.name
git config user.email
```

The name returned by `git config user.name` is **"you"** — the person reading this retro.

Run ALL of these git commands in parallel:

```bash
# 1. All commits in window
git log origin/main --since="<window>" --format="%H|%aN|%ae|%ai|%s" --shortstat

# 2. Per-commit LOC breakdown with author
git log origin/main --since="<window>" --format="COMMIT:%H|%aN" --numstat

# 3. Commit timestamps for session detection (Pacific time)
TZ=America/Los_Angeles git log origin/main --since="<window>" --format="%at|%aN|%ai|%s" | sort -n

# 4. Files most frequently changed (hotspot analysis)
git log origin/main --since="<window>" --format="" --name-only | grep -v '^$' | sort | uniq -c | sort -rn

# 5. PR numbers from commit messages
git log origin/main --since="<window>" --format="%s" | grep -oE '#[0-9]+' | sed 's/^#//' | sort -n | uniq | sed 's/^/#/'

# 6. Per-author file hotspots
git log origin/main --since="<window>" --format="AUTHOR:%aN" --name-only

# 7. Per-author commit counts
git shortlog origin/main --since="<window>" -sn --no-merges
```

### Step 2: Compute Metrics

| Metric | Value |
|--------|-------|
| Commits to main | N |
| Contributors | N |
| PRs merged | N |
| Total insertions | N |
| Total deletions | N |
| Net LOC added | N |
| Test LOC (insertions) | N |
| Test LOC ratio | N% |
| Active days | N |
| Detected sessions | N |
| Avg LOC/session-hour | N |

Then show a **per-author leaderboard**:

```
Contributor         Commits   +/-          Top area
You (name)               32   +2400/-300   browse/
alice                    12   +800/-150    app/services/
```

### Step 3: Commit Time Distribution

Show hourly histogram in Pacific time. Identify peak hours, dead zones, late-night clusters.

### Step 4: Work Session Detection

Detect sessions using **45-minute gap** threshold. Classify:
- **Deep sessions** (50+ min)
- **Medium sessions** (20-50 min)
- **Micro sessions** (<20 min)

### Step 5: Commit Type Breakdown

Categorize by conventional commit prefix (feat/fix/refactor/test/chore/docs). Flag if fix ratio exceeds 50%.

### Step 6: Hotspot Analysis

Top 10 most-changed files. Flag files changed 5+ times.

### Step 7: PR Size Distribution

Bucket PRs: Small (<100 LOC), Medium (100-500), Large (500-1500), XL (1500+).

### Step 8: Focus Score + Ship of the Week

- **Focus score:** % of commits in the most-changed top-level directory
- **Ship of the week:** Highest-LOC PR in the window

### Step 9: Team Member Analysis

For each contributor:
1. Commits, LOC, test ratio
2. Focus areas (top 3 directories)
3. Commit type mix
4. Session patterns
5. Biggest ship

For the current user: deepest treatment with personal focus score and session analysis.

For teammates: 2-3 sentences + specific **praise** (1-2 things) + **opportunity for growth** (1 thing).

### Step 10: Week-over-Week Trends (if window >= 14d)

Split into weekly buckets: commits, LOC, test ratio, fix ratio per week.

### Step 11: Streak Tracking

```bash
# Team streak
TZ=America/Los_Angeles git log origin/main --format="%ad" --date=format:"%Y-%m-%d" | sort -u

# Personal streak
TZ=America/Los_Angeles git log origin/main --author="<user_name>" --format="%ad" --date=format:"%Y-%m-%d" | sort -u
```

Count consecutive days with commits backward from today.

### Step 12: Load History & Compare

```bash
ls -t .context/retros/*.json 2>/dev/null
```

If prior retros exist, load the most recent and show deltas.

### Step 13: Save Retro History

```bash
mkdir -p .context/retros
```

Save JSON snapshot with metrics, authors, version range, streak, and tweetable summary.

### Step 14: Write the Narrative

Structure:
1. **Tweetable summary** (first line)
2. **Summary Table** (Step 2)
3. **Trends vs Last Retro** (if applicable)
4. **Time & Session Patterns** (Steps 3-4)
5. **Shipping Velocity** (Steps 5-7)
6. **Code Quality Signals** (test ratio, hotspots, XL PRs)
7. **Focus & Highlights** (Step 8)
8. **Your Week** (personal deep-dive)
9. **Team Breakdown** (per teammate, skip if solo)
10. **Top 3 Team Wins**
11. **3 Things to Improve**
12. **3 Habits for Next Week**
13. **Week-over-Week Trends** (if applicable)

## Compare Mode

When the user runs `/retro compare`:
1. Compute metrics for current window
2. Compute metrics for prior same-length window
3. Show side-by-side comparison with deltas
4. Narrative highlighting improvements and regressions

## Tone

- Encouraging but candid, no coddling
- Specific and concrete — always anchor in actual commits
- Skip generic praise — say exactly what was good
- Frame improvements as leveling up, not criticism
- Never compare teammates negatively
- Keep output around 3000-4500 words
- Output directly to conversation (only write `.context/retros/` JSON)

## Important Rules

- Use `origin/main` for all git queries
- Convert all timestamps to Pacific time
- If zero commits, say so and suggest a different window
- Round LOC/hour to nearest 50
- Do not read CLAUDE.md or other docs — this skill is self-contained
