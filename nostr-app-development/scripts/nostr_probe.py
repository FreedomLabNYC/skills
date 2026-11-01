#!/usr/bin/env python3
"""Stdlib-only Nostr relay probe: fetch events by author + kinds over websocket.

Usage:
    python3 nostr_probe.py <npub-or-64hex> [kinds-csv] [relay-host ...]
    # default kinds: 0 ; default relays: relay.primal.net nos.lol relay.damus.io nostrrelay.com

Probes kind-0 (profiles), kind-30311 (livestreams), or any kind list per relay.
Prints matching events' content per relay. A 503 handshake (relay.damus.io does
this intermittently) is transient -- rely on the other relays' answers.
"""
import socket, ssl, base64, os, json, struct, sys

DEFAULT_RELAYS = ["relay.primal.net", "nos.lol", "relay.damus.io", "nostrrelay.com"]
CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

def npub_to_hex(npub):
    """Decode npub1... to 64-char lowercase hex. 5->8 convertbits, NOT 5->4."""
    data = [CHARSET.index(c) for c in npub.split("1", 1)[1]][:-6]
    acc, bits, out = 0, 0, []
    for d in data:
        acc = (acc << 5) | d; bits += 5
        if bits >= 8:
            bits -= 8
            out.append((acc >> bits) & 0xFF)
    h = "".join("%02x" % b for b in out)
    if len(out) != 32:
        raise ValueError("bad npub: decoded to %d bytes, expected 32" % len(out))
    return h

def ws_connect(host, port=443):
    ctx = ssl.create_default_context()
    raw = socket.create_connection((host, port), timeout=15)
    s = ctx.wrap_socket(raw, server_hostname=host)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (f"GET / HTTP/1.1\r\nHost: {host}\r\n"
           f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
    s.sendall(req.encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        d = s.recv(4096)
        if not d:
            raise RuntimeError("handshake closed")
        buf += d
    head = buf.split(b"\r\n\r\n")[0].decode(errors="replace")
    if "101" not in head.split("\r\n")[0]:
        raise RuntimeError(f"no 101: {head.split(chr(10))[0]}")
    return s, buf.split(b"\r\n\r\n", 1)[1]

def send_text(s, msg):
    payload = msg.encode()
    hdr = bytearray([0x81])
    mask_key = os.urandom(4)
    n = len(payload)
    if n < 126:
        hdr.append(0x80 | n)
    elif n < 65536:
        hdr += bytearray([0x80 | 126]) + struct.pack(">H", n)
    else:
        hdr += bytearray([0x80 | 127]) + struct.pack(">Q", n)
    hdr += mask_key
    s.sendall(bytes(hdr) + bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload)))

def recv_frame(s, buf):
    def need(n):
        nonlocal buf
        while len(buf) < n:
            d = s.recv(4096)
            if not d:
                raise RuntimeError("closed")
            buf += d
        return buf[:n]
    b0, b1 = need(2)[0], need(2)[1]
    ln = b1 & 0x7F
    off = 2
    if ln == 126:
        ln = struct.unpack(">H", need(off + 2)[off:off + 2])[0]; off += 2
    elif ln == 127:
        ln = struct.unpack(">Q", need(off + 8)[off:off + 8])[0]; off += 8
    need(off + ln)
    frame = buf[off:off + ln]
    buf = buf[off + ln:]
    return b0 & 0x0F, frame, buf

def probe(pubkey, host, kinds, timeout=12):
    try:
        s, buf = ws_connect(host)
        send_text(s, json.dumps(["REQ", "p", {"authors": [pubkey], "kinds": kinds}]))
        s.settimeout(timeout)
        events = []
        try:
            while True:
                op, frame, buf = recv_frame(s, buf)
                if op == 0x8:
                    break
                if op != 0x1:
                    continue
                m = json.loads(frame)
                if m[0] == "EVENT" and m[1] == "p":
                    events.append(m[2])
                elif m[0] == "EOSE":
                    break
        except (socket.timeout, RuntimeError):
            pass
        s.close()
        return events
    except Exception as e:
        print(f"[{host}] ERROR: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    arg = sys.argv[1]
    pubkey = arg if len(arg) == 64 else npub_to_hex(arg)
    kinds = [int(k) for k in sys.argv[2].split(",")] if len(sys.argv) > 2 else [0]
    relays = sys.argv[3:] or DEFAULT_RELAYS
    seen = set()
    for host in relays:
        evs = probe(pubkey, host, kinds)
        if evs is None:
            continue
        fresh = [e for e in evs if e["id"] not in seen]
        seen.update(e["id"] for e in evs)
        print(f"[{host}] kind{kinds} events: {len(evs)} ({len(fresh)} new)")
        for e in evs:
            print(json.dumps(e, indent=1)[:1500])

if __name__ == "__main__":
    main()
