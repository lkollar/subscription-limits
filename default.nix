{
  lib,
  runCommand,
  makeWrapper,
  python3,
  callPackage,
  codexbar ? callPackage ./nix/codexbar.nix { },
}:
runCommand "subscription-limits-1.0.0"
  {
    nativeBuildInputs = [ makeWrapper ];
    meta = {
      description = "Private subscription limits PWA";
      mainProgram = "subscription-limits";
      platforms = [ "x86_64-linux" ];
    };
  }
  ''
    mkdir -p $out/bin $out/share/subscription-limits
    cp ${./server.py} $out/share/subscription-limits/server.py
    cp -r ${./web} $out/share/subscription-limits/web
    makeWrapper ${python3}/bin/python3 $out/bin/subscription-limits \
      --add-flags $out/share/subscription-limits/server.py \
      --set-default CODEXBAR_BIN ${codexbar}/bin/codexbar
  ''
