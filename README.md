# Subscription Limits

Minimal private iPhone PWA for Claude Code and Codex subscription limits.
Shows percentage left, five-hour/weekly reset countdowns, and last successful
refresh. Buildless HTML/CSS/JS; Python standard library; CodexBar Linux CLI.

## Run

Install CodexBar 0.74.0 and authenticate Claude Code and Codex locally first.

```sh
CODEXBAR_BIN=/path/to/codexbar PUBLIC_HOST=your-server.example python3 server.py
```

Binds only to `127.0.0.1:18740`. Serve at `/limits/` through a private reverse
proxy. iPhone: open in Safari, Share → Add to Home Screen. No browser login or
credentials are sent to the PWA. The first online visit saves an offline shell.

## NixOS

The flake exports `packages.x86_64-linux.default`, `codexbar`, and
`nixosModules.default`. The module installs pinned Python/CodexBar dependencies,
runs a systemd user service, enables lingering for the selected user, and can
add a private Tailscale Serve route without replacing existing routes.

```nix
# Import this flake's nixosModules.default into your host modules.
services.subscription-limits = {
  enable = true;
  user = "your-user";
  serve.enable = true;
  serve.httpsPort = 8443;
  # Optional: claudePackage = unstablePkgs.claude-code;
};
```

The public hostname is resolved from Tailscale at runtime when Serve is enabled;
it is never baked into the package. Port 8443 avoids an existing proxy on 443.
Do not enable Funnel. A conflicting existing `/limits` handler is rejected.
The module remains scoped to one configured user's existing provider logins.

```sh
nix build .#default --no-link
nix run .#default
```

Only x86_64 Linux is packaged: the official static musl release is pinned to
0.74.0 with SHA256
`e7b0bdc6d6931a4e6fd5ce4037e1125a073ec6cf38cd72f1b3bd8aeecfde51f5`.
[CodexBar CLI docs](https://github.com/steipete/CodexBar/blob/main/docs/cli.md).
CodexBar remains an independently licensed upstream dependency; no release
binary, credentials or runtime data are committed here.

## Collector contract and privacy

The CLI JSON root is an array. The allowlist reads only `provider`,
`usage.updatedAt`, `primary` (300 minutes), and `secondary` (10080 minutes).
The API retains `usedPercent`; the UI fills bars with `100 - usedPercent` and
labels them “left”. Missing or invalid windows never become zero usage.

Each provider refreshes every five minutes. Failed collection, age over fifteen
minutes, or a passed reset marks retained readings stale. Each invocation has
a 45-second timeout; manual requests are coalesced and limited to once a minute.
Claude's supported CLI fallback can renew its saved login after an OAuth auth
error. Codex uses OAuth only. No direct token-refresh code is added.

Last-good normalized readings are 0600 in
`~/.local/state/subscription-limits/last-good.json`. The browser stores only that
sanitized API shape. Offline readings always say stale. The service worker
caches assets only. Raw identity, email, tokens, credits and provider errors
are never forwarded. Local processes can access the loopback API, and tailnet
access follows your Tailscale ACLs. Provider credentials stay outside Git/Nix.

## Test and operate

```sh
python3 -m unittest discover -s tests
node --check web/app.js
node --check web/sw.js
nix develop --command python3 tests/browser.py
nix develop --command python3 tests/reset_ui.py
LIMITS_URL=https://your-server.example:8443/limits/ \
nix develop --command python3 tests/https.py
systemctl --user status subscription-limits
journalctl --user -u subscription-limits -n 30
```

Browser tests need a running app with both providers authenticated. Screenshots
are written outside the repo. Optional `LIVE_USAGE_JSON` reads a private probe
for schema validation; no probe is part of the test fixtures or package.
`LIMITS_HOST_IP` supports explicit hostname resolution in HTTPS browser checks.
Reset timestamps use the phone’s timezone alongside countdowns. Codex saved
resets expose only the reported available count and expiry timestamps; Claude
saved resets stay unavailable. Failed or expired readings show the saved count
as "at last refresh". Expanding the row reveals expiry dates; it cannot redeem
resets.

Fixtures are synthetic. Never commit probe JSON, OAuth state, screenshots or
private environment files. Unit tests run without provider credentials.

The standalone service template is an alternative for manual installation;
NixOS users should use the module. When migrating, archive/remove a previous
`~/.config/systemd/user/subscription-limits.service` so it cannot override the
NixOS-managed unit. Keep the same state directory and existing logins.
