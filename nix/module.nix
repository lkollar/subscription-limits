{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.subscription-limits;
  userHome = config.users.users.${cfg.user}.home;
  publicHost =
    if cfg.publicHost != "" then
      lib.escapeShellArg cfg.publicHost
    else if cfg.serve.enable then
      ''
        "$(${pkgs.tailscale}/bin/tailscale status --json | ${pkgs.jq}/bin/jq -er '.Self.DNSName | rtrimstr(".")')"
      ''
    else
      "localhost";
  launcher = pkgs.writeShellScript "subscription-limits-start" ''
    set -eu
    export PUBLIC_HOST=${publicHost}
    exec ${cfg.package}/bin/subscription-limits
  '';
  routeCheck = ./serve-guard.py;
in
{
  options.services.subscription-limits = {
    enable = lib.mkEnableOption "subscription limits PWA";
    user = lib.mkOption {
      type = lib.types.str;
      description = "User owning existing provider logins.";
    };
    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.callPackage ../default.nix { };
    };
    codexbarPackage = lib.mkOption {
      type = lib.types.package;
      default = pkgs.callPackage ./codexbar.nix { };
    };
    claudePackage = lib.mkOption {
      type = lib.types.package;
      default = pkgs.claude-code;
    };
    publicHost = lib.mkOption {
      type = lib.types.str;
      default = "";
      description = "Allowed hostname; empty resolves Tailscale at runtime when Serve is enabled.";
    };
    serve.enable = lib.mkEnableOption "private Tailscale Serve route";
    serve.httpsPort = lib.mkOption {
      type = lib.types.port;
      default = 8443;
    };
  };
  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = builtins.hasAttr cfg.user config.users.users;
        message = "subscription-limits.user must name an existing user";
      }
    ];
    environment.systemPackages = [
      cfg.package
      cfg.codexbarPackage
    ];
    users.users.${cfg.user}.linger = true;
    systemd.tmpfiles.rules = [
      "d ${userHome}/.codexbar 0700 ${cfg.user} - -"
      "d ${userHome}/.config/codexbar 0700 ${cfg.user} - -"
    ];
    systemd.user.services.subscription-limits = {
      description = "Claude Code and Codex subscription limits";
      wantedBy = [ "default.target" ];
      unitConfig.ConditionUser = cfg.user;
      path = [
        cfg.claudePackage
        cfg.codexbarPackage
        pkgs.coreutils
      ];
      environment = {
        PYTHONUNBUFFERED = "1";
        CODEXBAR_BIN = "${cfg.codexbarPackage}/bin/codexbar";
      };
      serviceConfig = {
        Type = "simple";
        ExecStart = launcher;
        StateDirectory = "subscription-limits";
        StateDirectoryMode = "0700";
        Restart = "on-failure";
        RestartSec = 10;
        TimeoutStopSec = 15;
        KillMode = "control-group";
        UMask = "0077";
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        ReadWritePaths = [
          "-%h/.claude"
          "-%h/.claude.json"
          "-%h/.codex"
          "-%h/.codexbar"
          "-%h/.config/codexbar"
          "-%h/.cache"
        ];
        RestrictAddressFamilies = [
          "AF_UNIX"
          "AF_INET"
          "AF_INET6"
        ];
      };
    };
    services.tailscale.enable = lib.mkIf cfg.serve.enable true;
    systemd.services.subscription-limits-serve = lib.mkIf cfg.serve.enable {
      description = "Private subscription limits Tailscale route";
      wantedBy = [ "multi-user.target" ];
      requires = [ "tailscaled.service" ];
      after = [ "tailscaled.service" ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        UMask = "0077";
        StateDirectory = "subscription-limits-serve";
      };
      script = ''
        set -eu
        host=$(${pkgs.tailscale}/bin/tailscale status --json | ${pkgs.jq}/bin/jq -er '.Self.DNSName | rtrimstr(".")'):${toString cfg.serve.httpsPort}
        state=/var/lib/subscription-limits-serve
        ${pkgs.tailscale}/bin/tailscale serve status --json > "$state/before.json"
        ${pkgs.python3}/bin/python3 ${routeCheck} "$state/before.json" "$host"
        ${pkgs.tailscale}/bin/tailscale serve --bg --https=${toString cfg.serve.httpsPort} --set-path=/limits --yes http://127.0.0.1:18740
        ${pkgs.tailscale}/bin/tailscale serve status --json > "$state/after.json"
        ${pkgs.python3}/bin/python3 ${routeCheck} "$state/before.json" "$host" "$state/after.json"
      '';
    };
  };
}
