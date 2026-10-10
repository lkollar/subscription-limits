{
  description = "Private Claude Code and Codex subscription limits PWA";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
  outputs =
    { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in
    {
      packages.${system} = {
        default = pkgs.callPackage ./default.nix { };
        codexbar = pkgs.callPackage ./nix/codexbar.nix { };
      };
      nixosModules.default = import ./nix/module.nix;
      devShells.${system}.default = pkgs.mkShell {
        packages = [
          pkgs.nodejs
          pkgs.chromium
          (pkgs.python3.withPackages (ps: [ ps.playwright ]))
        ];
      };
      checks.${system}.unit =
        pkgs.runCommand "subscription-limits-tests"
          {
            nativeBuildInputs = [
              pkgs.python3
              pkgs.nodejs
            ];
          }
          ''
            cp -r ${./server.py} server.py
            mkdir tests nix
            cp ${./tests/test_server.py} tests/test_server.py
            cp ${./tests/test_serve_guard.py} tests/test_serve_guard.py
            cp ${./nix/serve-guard.py} nix/serve-guard.py
            python3 -m unittest discover -s tests
            node --check ${./web/app.js}
            node --check ${./web/sw.js}
            touch $out
          '';
    };
}
