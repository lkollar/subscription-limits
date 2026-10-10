# Subscription limits
<!-- impeccable:product-schema 1 -->

## Platform
web

## Stack
Confirmed: buildless HTML/CSS/JS and a small Python server; build directly.

## Users
Server owner checking Claude Code and Codex subscription limits on iPhone.

## Product Purpose
Show five-hour and weekly remaining percentages, reset countdowns, and each
provider's last successful refresh. Make stale and unavailable data explicit.

## Operating Context
the server NixOS, CodexBar Linux CLI, existing server-side OAuth credentials,
systemd user service, private HTTPS through Tailscale Serve. Preserve routes.

## Capabilities and Constraints
Minimal installable iPhone PWA, iOS manifest and icons, offline app shell.
Credentials remain server-side. Test with real usage. No invented quota values.
