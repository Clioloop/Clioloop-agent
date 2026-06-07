# nix/desktop.nix — Clio Desktop (Electron) app build + wrapper
#
# `clioAgent` is the fully-built `.#default` package — it ships the
# `clio` binary with the venv, runtime PATH, bundled skills/plugins, etc.
# already wired up.  We point the desktop at it via the existing
# `CLIO_DESKTOP_CLIO` override env var, so the desktop's resolver
# uses our fully wrapped binary at step 4 ("existing Clio CLI").
# No reimplementation of the agent resolution in this wrapper.
{ pkgs, lib, stdenv, makeWrapper, clioNpmLib, electron, clioAgent, ... }:
let
  npm = clioNpmLib.mkNpmPassthru { folder = "apps/desktop"; attr = "desktop"; pname = "clio-desktop"; };

  packageJson = builtins.fromJSON (builtins.readFile (npm.src + "/apps/desktop/package.json"));
  version = packageJson.version;

  # Build the renderer (dist/ + electron/ + package.json).
  renderer = pkgs.buildNpmPackage (npm // {
    pname = "clio-desktop-renderer";
    inherit version;

    doCheck = false;
    # The workspace lockfile resolves all peer deps
    # correctly so --legacy-peer-deps is not needed.
    # --ignore-scripts comes from mkNpmPassthru (shared).
    makeCacheWritable = true;

    buildPhase = ''
      runHook preBuild

      # write-build-stamp.cjs replacement.  Packaged Electron reads this
      # at first-launch to pin the install.ps1 git ref; informational in
      # nix builds (the backend comes from the derivation directly).
      mkdir -p apps/desktop/build
      echo '{"schemaVersion":1,"commit":"nix","branch":"nix","dirty":false,"source":"nix"}' > apps/desktop/build/install-stamp.json

      # Build from apps/desktop/ so vite.config.ts resolves correctly.
      # The workspace root's node_modules/ is accessible as ../../node_modules/.
      cd apps/desktop

      # vite handles TS transpilation via esbuild — no type-checking.
      # We skip `tsc -b` to avoid type errors in test files that don't
      # ship in the bundle (real upstream peer-dep version mismatches
      # in @testing-library/react v16 — not blocking the build).
      # Call vite directly from root node_modules to avoid npx resolving
      # through unpatched workspace symlinks.
      node ../../node_modules/vite/bin/vite.js build --outDir dist

      # Return to source root so installPhase paths are correct.
      cd ../..

      runHook postBuild
    '';

    installPhase = ''
      runHook preInstall
      mkdir -p $out
      # vite writes to apps/desktop/dist/ (we cd'd there in buildPhase).
      # apps/desktop/build was created before the cd.  electron/ is source.
      cp -r apps/desktop/dist $out/
      cp -r apps/desktop/electron $out/
      cp -r apps/desktop/build $out/
      cp apps/desktop/package.json $out/
      runHook postInstall
    '';
  });
in

# Electron wrapper: nixpkgs' electron binary pointed at the renderer dir.
stdenv.mkDerivation {
  pname = "clio-desktop";
  inherit version;

  dontUnpack = true;
  dontBuild = true;

  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    runHook preInstall

    mkdir -p $out/share/clio-desktop $out/bin
    cp -r ${renderer}/* $out/share/clio-desktop/

    # Wrap the nixpkgs electron binary to launch our app.  Set
    # CLIO_DESKTOP_CLIO to the absolute path of the nix-built `clio`
    # binary so the desktop's resolver step 4 ("existing Clio CLI on
    # PATH") uses our fully wrapped binary — venv with all deps,
    # bundled skills/plugins, runtime PATH (ripgrep/git/ffmpeg/etc).
    # No reimplementation of the agent resolver in the wrapper.
    makeWrapper ${lib.getExe electron} $out/bin/clio-desktop \
      --add-flags "$out/share/clio-desktop" \
      --set CLIO_DESKTOP_CLIO "${lib.getExe clioAgent}" \
      --set ELECTRON_IS_DEV 0

    runHook postInstall
  '';

  passthru = {
    inherit (renderer.passthru) packageJsonPath;
  };

  meta = with lib; {
    description = "Native Electron desktop shell for Clio Agent";
    homepage = "https://github.com/Clioloop/Clioloop-agent";
    license = licenses.mit;
    platforms = platforms.unix;
    mainProgram = "clio-desktop";
  };
}
