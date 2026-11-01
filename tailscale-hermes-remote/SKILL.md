---
name: tailscale-hermes-remote
description: "Use when Hermes app can't reach dashboard :9119 off-LAN."
version: 1.0.0
author: Freedom Lab NYC
license: MIT
metadata:
  hermes:
    tags: [tailscale, remote-access, hermes-dashboard]
    related_skills: [hermes-agent]
---

# Tailscale remote access to the Hermes dashboard

## When to Use
The official Hermes app (iOS/desktop) or any remote client can't reach the host dashboard on port 9119 while off the home LAN; or the tailnet setup needs to be redone/verified on a new device.

Goal: the official Hermes app (iOS/desktop) reaches your dashboard `:9119` from anywhere. SSH stays off (port 22 not exposed, keep it that way). Tailscale is the approved path — outbound-only, device-paired, nothing new exposed to the internet.

## Current state
Live node/party data intentionally NOT stored here (skill is shareable): get it with `tailscale status` / `tailscale ip -4` on your host; detailed status belongs in the operator's private project notes, never in a shared skill.
- tailscale installed via pacman, `tailscaled` systemd-enabled, dashboard on `:9119` with basic auth.
- Credentials (username + password): `~/.hermes/.env` → `HERMES_DASHBOARD_BASIC_AUTH_USERNAME` / `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD`. NEVER write their values into this skill or any shared note. Password is flagged rotate-me since the dashboard is tailnet-wide.

## Host setup (needs sudo → the user pastes these; agent does the rest)
```
sudo pacman -S --noconfirm tailscale
sudo systemctl enable --now tailscaled
sudo tailscale set --operator=$USER        # else tailscale CLI fails: "checkprefs access denied"
sudo ufw allow in on tailscale0 to any port 9119 proto tcp comment 'hermes tailscale'
```
Rule scope: open ONLY tcp/9119 on tailscale0 — not the blanket `allow in on tailscale0`.

Then (agent, as operator — no sudo): `tailscale up` prints an auth URL like `https://login.tailscale.com/a/xxxx` and BLOCKS until approved. Run it backgrounded, poll for the URL, hand it to the user.

**Pitfall:** "logged in successful" in the browser ≠ done. The device must also be **approved** ("Add device" for *your host*) on that auth page; host stays `NeedsLogin` until then. Re-open the same URL if it skipped to the admin console.

## Verify
1. `tailscale status` → peer list, host shows 100.x line without `NeedsLogin`.
2. `curl -s -o /dev/null -w '%{http_code}' http://<100.x>:9119/` → **302** = healthy (auth redirect). 000 = problem.
3. `tailscale ping -c 3 <peer-100.x>` from host → pong proves tunnel both ways (LAN-peer route fine at home, DERP fine off-LAN).
4. ufw check: `grep -A3 tailscale /etc/ufw/user.rules`.

## Devices
Install Tailscale (App Store / tailscale.com/download), same account, toggle ON. Hermes app connection: `http://<tailscale-ip>:9119` (read the IP via `tailscale ip -4` on the host), Password sign-in with the `.env` credentials. Works on LTE; on home Wi-Fi the LAN address also works.

## Maintenance
- **Key expiry:** ~180 days after auth node silently drops → re-auth `sudo tailscale up`, or flip "Disable key expiry" for the host in the Tailscale admin console.
- **App hangs at "Finding your Hermes…"** → order of checks: `tailscale status` (logged in? peer there?) → ufw tailscale0 rule → `ss -tlnp | grep 9119`.
- **Rotate dashboard password** when convenient (exposed tailnet-wide): set new value in `~/.hermes/.env` and restart dashboard; scrypt hash must match or logins fail.
