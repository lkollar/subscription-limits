{
  lib,
  stdenvNoCC,
  fetchurl,
}:
stdenvNoCC.mkDerivation {
  pname = "codexbar-cli";
  version = "0.74.0";
  src = fetchurl {
    url = "https://github.com/steipete/CodexBar/releases/download/v0.74.0/CodexBarCLI-v0.74.0-linux-musl-x86_64.tar.gz";
    hash = "sha256-57C9xtaTGk5v1c5AN+ESWgc+xs84zXLxs72K7s/eUfU=";
  };
  sourceRoot = ".";
  dontConfigure = true;
  dontBuild = true;
  installPhase = ''
    mkdir -p $out/bin $out/libexec/codexbar
    cp CodexBarCLI VERSION $out/libexec/codexbar/
    cp -r CodexBar_CodexBarCore.bundle $out/libexec/codexbar/
    ln -s ../libexec/codexbar/CodexBarCLI $out/bin/codexbar
  '';
  meta = {
    description = "CodexBar Linux usage collector";
    homepage = "https://github.com/steipete/CodexBar";
    license = lib.licenses.mit;
    mainProgram = "codexbar";
    platforms = [ "x86_64-linux" ];
  };
}
