---
name: stress-test
description: Reusable testing and bug-hunting checklist for any workflow, script, server, or integration we build. Use after building anything new — scripts, APIs, cron jobs, GitHub Actions, static sites, launchd services, or agent tools. Covers immediate validation, adversarial testing, and deployment verification.
---

# Stress Test

Run this checklist after building or significantly modifying any system. Adapt to context — not every item applies to every build. But read every item and consciously skip, don't just skim past.

## Layer 1: Does It Actually Work?

### 1.1 Run with real data
Don't mock it. Hit the real API, real files, real paths. If it worked with test data but fails with real data, it doesn't work.

### 1.2 Run from the actual execution context
If it runs via cron → test from a cron-triggered session, not your interactive shell.
If it runs via launchd → `launchctl kickstart gui/$(id -u)/<label>`, don't just `python3 script.py`.
If it runs via GitHub Action → trigger `workflow_dispatch`, don't just run locally.
The #1 cause of "works on my machine" is different PATH, env vars, and working directories.

### 1.3 Check the output
Read the logs. Read the actual file it wrote. Open the actual page it deployed. Don't just check the exit code.

### 1.4 Verify idempotency
Run it twice in a row. Does it double-create resources? Double-schedule jobs? Duplicate rows? Overwrite good data with stale data?

### 1.5 Repeated runs (the "5x test")
Run the full workflow 5 times consecutively. Check:
- Is the output identical each time? (diff the outputs)
- Do any runs fail intermittently? (flaky API calls, token timing, rate limits)
- Do side effects accumulate? (temp files, backup files, log entries growing unbounded)
- Does performance degrade across runs? (memory, disk, API quota)
If any run produces a different result, that's a bug — not "flakiness to accept."

## Layer 2: What Breaks It?

### 2.1 Bad input
- API returns empty response, 403, 500, malformed JSON, HTML error page
- Required fields are null or missing
- Unicode characters in names/strings
- Unexpectedly large response (100x normal)
- Rate limited (429)

### 2.2 Missing dependencies
- Network is down (airplane mode test)
- Token expired or revoked
- Expected file doesn't exist
- Expected service isn't running (phoenixd down, API server not started)
- Disk full / permissions denied

### 2.3 Timing failures
- Mac was asleep when launchd plist was supposed to fire — does it fire on wake or silently miss?
- Two instances run simultaneously (race condition from overlapping cron triggers)
- Upstream data changed between when you read it and when you act on it

### 2.4 State corruption
- Kill the script mid-execution. Is the state file half-written? Is the JSON invalid? Is the plist loaded but pointing to a deleted script?
- What happens on partial failure? (3 of 5 API calls succeeded — are the 3 saved or is everything rolled back?)

### 2.5 Silent failures
**This is the most dangerous category.** Check:
- Does the script exit 0 even on failure?
- Does the cron job report "ok" status even when it accomplished nothing?
- Is there any monitoring that would tell us if this stopped working for a week?
- If the GitHub Action fails, do we find out? Or does the site just get stale?

## Layer 3: Deployment Verification

### 3.1 Logging
Every automated script must log:
- When it ran
- What it did (not just errors — the happy path too)
- Enough detail to debug without re-running

### 3.2 Monitoring hooks
For anything that runs on a schedule:
- How would we know if it silently stopped working?
- Is there a "last successful run" timestamp we can check?
- Can a heartbeat spot-check it?

### 3.3 Credential lifecycle
- When does the token/key expire?
- What happens when it does — graceful error or silent failure?
- Is the credential hardcoded, or in a central config file?
- Is the credential committed to git? (It shouldn't be, but check.)

### 3.4 Recovery
- If the Mac reboots, does this come back up automatically?
- If we need to rebuild from scratch, is there a README that documents how?
- Are there manual steps that only exist in our conversation history?

## Layer 4: For Specific Build Types

### API Servers
- [ ] Hit every endpoint (GET, POST, bad method)
- [ ] Send malformed JSON — does it 400 or crash?
- [ ] Send oversized payload — is there a limit?
- [ ] CORS headers present?
- [ ] What happens if the upstream it depends on is down?

### Cron / Scheduled Jobs
- [ ] Check `openclaw cron list` — is status `ok` or `error`?
- [ ] Verify the schedule fires when expected (check `Last` column)
- [ ] Timeout set appropriately? (default 30s may be too short)
- [ ] What happens if the previous run hasn't finished when the next trigger fires?

### LaunchAgents / Services
- [ ] `launchctl list | grep <label>` — is it loaded?
- [ ] PID column shows a number (running) vs `-` (not running)?
- [ ] Status column shows `0` (clean) vs error code?
- [ ] `ThrottleInterval` set to prevent crash loops?
- [ ] Log rotation — will stdout/stderr logs grow forever?

### Static Sites / GitHub Pages
- [ ] Hard refresh after deploy — cached CSS/JS can mask broken changes
- [ ] Mobile viewport check — layout breaks often invisible on desktop
- [ ] OG preview tags present? (test with a link preview tool)
- [ ] All internal links work? (`find . -name "*.html" | xargs grep 'href="/' | ...`)
- [ ] Assets load? (check browser dev tools network tab for 404s)

### GitHub Actions
- [ ] Check Actions tab — is it actually running on schedule?
- [ ] Read the run logs for warnings, not just green checkmarks
- [ ] Does `workflow_dispatch` trigger work? (test with curl)
- [ ] Permissions — does the token/bot have write access to push commits?

## How to Use

After building something:
1. Read through the checklist
2. Mark items as N/A, PASS, or FAIL
3. Fix all FAILs before declaring it done
4. For any "I'm not sure" — that's a FAIL until proven otherwise
