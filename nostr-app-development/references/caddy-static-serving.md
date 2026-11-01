# Serving static files from a Caddy v2 site block (thumbnail hosting pattern)

Goal: nostr clients must fetch an image over public HTTPS, so panel-generated
stills get scp'd to the streaming VPS and served under the existing TLS hostname.

## Working Caddyfile shape

Inside the site block, BEFORE the catch-all `reverse_proxy`:

```
@thumbs path /thumbs/*
handle @thumbs {
  root * /var/www/thumbs
  uri strip_prefix /thumbs
  file_server
}
```

- Use `@matcher` + `handle`, not bare `handle_path` — in some Caddy versions
  `handle_path` outside proper grouping misroutes to the reverse proxy (404s even
  though the file exists on disk).
- A `redir` directive placed outside a handle is invalid config; omit it.
- Back up the Caddyfile first, then validate and reload:
  `caddy validate --config /etc/caddy/Caddyfile && systemctl reload caddy`.

## Verifying behind Cloudflare

If the hostname's DNS record is CF-proxied, public curl hits the edge, not your
origin — a stale edge 404 can mask a working origin. Test the origin directly,
run ON the VPS:

```
curl -o /dev/null -w "%{http_code}\n" --resolve host.example:443:127.0.0.1 https://host.example/thumbs/file.png
```

200 locally + 404 publicly = edge cache (wait or purge); 404 locally too =
Caddyfile problem, re-check matcher placement.

## Publisher script contract

`scp <local-file> vps:/var/www/thumbs/<name>` then echo the final URL as the last
stdout line; keep URL construction in one place so announce code just embeds what
it gets back.
