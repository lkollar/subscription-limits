"""Reject destructive Serve updates before calling Tailscale."""
import json
import sys


def check(before, host, after=None):
    port = host.rsplit(":", 1)[1]
    tcp = before.get("TCP", {}).get(port)
    if tcp is not None and tcp != {"HTTPS": True}:
        raise ValueError("Existing port configuration conflicts; left untouched")
    handlers = before.get("Web", {}).get(host, {}).get("Handlers", {})
    if "/limits/" in handlers:
        raise ValueError("Existing /limits/ route conflicts; left untouched")
    handler = handlers.get("/limits")
    if handler is not None and handler != {"Proxy": "http://127.0.0.1:18740"}:
        raise ValueError("Existing /limits route conflicts; left untouched")
    if before.get("AllowFunnel", {}).get(host, False):
        raise ValueError("Existing port has Funnel enabled; app must remain private")
    if after is None:
        return
    for name, web in before.get("Web", {}).items():
        for path, value in web.get("Handlers", {}).items():
            if after.get("Web", {}).get(name, {}).get("Handlers", {}).get(path) != value:
                raise ValueError("Existing route changed")
    for key in ("TCP", "AllowFunnel"):
        for name, value in before.get(key, {}).items():
            if after.get(key, {}).get(name) != value:
                raise ValueError("Existing serve setting changed")
    if after.get("Web", {}).get(host, {}).get("Handlers", {}).get("/limits") != {"Proxy": "http://127.0.0.1:18740"}:
        raise ValueError("Expected private route missing")
    if after.get("AllowFunnel", {}).get(host, False):
        raise ValueError("App route must remain private")


if __name__ == "__main__":
    try:
        before = json.load(open(sys.argv[1]))
        after = json.load(open(sys.argv[3])) if len(sys.argv) == 4 else None
        check(before, sys.argv[2], after)
    except ValueError as error:
        raise SystemExit(str(error))
