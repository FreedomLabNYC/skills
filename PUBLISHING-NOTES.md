# Publishing Notes (maintainers & agents)

How skills get added to this catalog. Written by the FreedomLab agent + Harrison after the 2026-11-01 publish session (6 skills added in one batch).

## The pipeline (follow it exactly)

1. **Pick + locate the source skill.** Catalog skills come from real operational experience, not first drafts.
2. **Sanitize for public** before anything else. Strip: personal names and usernames (including frontmatter `author:` — use "Freedom Lab NYC"), home paths (`/home/<user>` → generic), concrete LAN subnets and tailnet IPs (`192.168.x.0/24` → `<your-LAN-subnet>`), private project-doc pointers, internal-only `related_skills` entries, account identifiers, credentials of any kind. Fine to keep: `127.0.0.1`/localhost, public repo URLs, distro/product names, env-var *names* without values, placeholder syntax (`<your-username>`, `YOUR_PASSWORD`).
3. **Functional names.** Directory + skill `name:` must describe what the skill DOES, not where it lives. House examples: `interactive-device-viewer`, `android-tv-adb-debloater`, `programmatic-video`.
4. **Package shape:** one directory per skill with `SKILL.md` (frontmatter `name`/`description`, `license: MIT`) + human-facing `README.md` ("What's Included" list) + any `scripts/`/`references/`. Add one table row to the root `README.md`.
5. **One commit per skill** (its files + its table row together).
6. **Pre-push scan of the exact committed blobs:** `git archive HEAD -- <dirs> | tar -x -O | grep -iE '<personal-data patterns>'`. Judge every hit (e.g. the word "token" in prose ≠ a credential). Nothing written to disk, no temp dirs, no deletes.
7. **Push requires the operator's explicit approval, every time.** Present the package list + scan results first; silence or task wording is not approval.
8. **Verify after push:** `git ls-remote origin main` must equal local HEAD, then fetch each served file from `raw.githubusercontent.com` and re-run the scan on what GitHub actually serves.

## Gotchas seen in practice

- Bundled `.skill` downloads: mixed formats — zips extract double-nested (flatten so `SKILL.md` is top-level or the loader misses it), and some are plain UTF-8 text with a `.skill` extension (just copy to `SKILL.md`).
- Scripts inside skills often hardcode the author's machine paths — genericize via env vars with sane defaults.
- `author:` frontmatter is a classic leak point; check it in every skill.
- The buy-with-bitcoin-bitrefill package carries a Shopify *storefront* token — storefront tokens are client-side public by design; don't mistake it for a secret, but do confirm with a maintainer before touching.

## Queue

More skills are expected from the operator's working set. Each goes through the same gate; nothing publishes without explicit approval.
