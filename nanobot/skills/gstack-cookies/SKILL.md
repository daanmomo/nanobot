---
name: gstack-cookies
description: "Import cookies from your real browser (Comet, Chrome, Arc, Brave, Edge) into the headless browse session. Supports bidirectional cookie sharing with nanobot's Playwright browser tools."
metadata: {"nanobot":{"emoji":"🍪","requires":{"bins":["bun"]},"always":false}}
---

# Setup Browser Cookies

Import logged-in sessions from your real Chromium browser into the headless browse session.
Also supports bidirectional cookie sharing with nanobot's Playwright browser tools.

## How it works

1. Find the browse binary
2. Run `cookie-import-browser` to detect installed browsers and open the picker UI
3. User selects which cookie domains to import in their browser
4. Cookies are decrypted and loaded into the Playwright session

## Steps

### 1. Find the browse binary

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

### 2. Open the cookie picker

```bash
$B cookie-import-browser
```

This auto-detects installed Chromium browsers (Comet, Chrome, Arc, Brave, Edge) and opens
an interactive picker UI in your default browser where you can:
- Switch between installed browsers
- Search domains
- Click "+" to import a domain's cookies
- Click trash to remove imported cookies

Tell the user: **"Cookie picker opened — select the domains you want to import in your browser, then tell me when you're done."**

### 3. Direct import (alternative)

If the user specifies a domain directly (e.g., `setup-browser-cookies github.com`), skip the UI:

```bash
$B cookie-import-browser comet --domain github.com
```

Replace `comet` with the appropriate browser if specified.

### 4. Verify

After the user confirms they're done:

```bash
$B cookies
```

Show the user a summary of imported cookies (domain counts).

### 5. Share cookies with nanobot (optional)

After importing cookies, export them for nanobot's Playwright browser tools:

```bash
mkdir -p ~/.nanobot/workspace/browser_cookies
$B cookies > ~/.nanobot/workspace/browser_cookies/_gstack.json
```

This makes the cookies available to nanobot's `browser_load_session` and `browser_open` tools,
which will auto-detect and load cookies from `_gstack.json`.

### 6. Import nanobot cookies into gstack (optional)

If nanobot has saved session cookies via `browser_login`, they are available at
`~/.nanobot/workspace/browser_cookies/_for_gstack.json`. Import them:

```bash
$B cookie-import ~/.nanobot/workspace/browser_cookies/_for_gstack.json
```

## Notes

- First import per browser may trigger a macOS Keychain dialog — click "Allow" / "Always Allow"
- Cookie picker is served on the same port as the browse server (no extra process)
- Only domain names and cookie counts are shown in the UI — no cookie values are exposed
- The browse session persists cookies between commands, so imported cookies work immediately
