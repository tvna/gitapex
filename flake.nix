{
  description = "gitapex external toolchain (SSoT for uv/gh/actionlint/zizmor/python/bun/lychee + apm/rtk/betterleaks)";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { nixpkgs, ... }:
    let
      systems = [ "aarch64-linux" "x86_64-linux" "aarch64-darwin" "x86_64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;

      # --- Class B helper: one SHA-pinned prebuilt release binary ---
      # The only axes that vary between tools are: archive type (.zip needs
      # unzip), whether it is a bare single binary vs a directory bundle that
      # must be kept intact, the in-archive binary name, and the pin data.
      # `kind` selects the install strategy; everything else is shared here so
      # the per-tool blocks below carry only the pin tables + a few literals.
      #
      # dontPatchELF: prebuilt binaries are installed as-is. On a standard FHS
      # Linux (including ubuntu CI) and on macOS the dynamic loader resolves
      # normally. Dynamically-linked Linux builds (apm's PyInstaller loader,
      # rtk's aarch64 gnu build) are NOT patched for non-FHS hosts such as
      # NixOS or minimal/distroless containers -- a known limitation; a
      # Linux-capable follow-up may add autoPatchelfHook + the needed libs.
      mkReleaseBinary = pkgs: { pname, version, url, sha256, kind, binInArchive ? pname }:
        let
          isZip = pkgs.lib.hasSuffix ".zip" url;
          common = {
            inherit pname version;
            src = pkgs.fetchurl { inherit url sha256; };
            dontBuild = true;
            dontStrip = true;
            dontPatchELF = true;
            nativeBuildInputs =
              (pkgs.lib.optional isZip pkgs.unzip)
              ++ (pkgs.lib.optional (kind == "wrapperDir") pkgs.makeWrapper);
          };
          byKind = {
            # Bare archive: a single binary (possibly beside LICENSE/README,
            # or a .zip that drops the exec bit) sits at the archive root.
            binary = {
              sourceRoot = ".";
              installPhase = ''
                runHook preInstall
                install -Dm755 ${binInArchive} $out/bin/${pname}
                runHook postInstall
              '';
            };
            # Directory bundle: the archive holds one top-level dir (Nix's
            # default unpackPhase auto-descends into it) containing the binary
            # plus support files (e.g. apm's _internal/ PyInstaller tree) that
            # MUST stay beside it at runtime. Copy the whole tree, wrap the bin.
            wrapperDir = {
              installPhase = ''
                runHook preInstall
                mkdir -p $out/libexec/${pname}
                cp -r . $out/libexec/${pname}/
                chmod +x $out/libexec/${pname}/${binInArchive}
                makeWrapper $out/libexec/${pname}/${binInArchive} $out/bin/${pname}
                runHook postInstall
              '';
            };
          };
        in
        pkgs.stdenvNoCC.mkDerivation (common // byKind.${kind});

      # --- Class B pin tables: one record per tool, keyed by system ---
      # asset + sha256 (+ bin where the in-archive name is not the pname) are
      # STATIC string literals so a regex updater can bump them in place.
      classBData = {
        # apm 0.25.0 -- tag v0.25.0. Each asset unpacks to a single dir
        # apm-<os>-<arch>/ holding `apm` (thin PyInstaller loader) + _internal/.
        apm = {
          aarch64-linux  = { asset = "apm-linux-arm64.tar.gz";   sha256 = "sha256-li0NRjVEvbpC8smejaoS7vKr0V1S4Yv7utB/sT5XMwU="; };
          x86_64-linux   = { asset = "apm-linux-x86_64.tar.gz";  sha256 = "sha256-ekKB75Felgn4hB7O0ZKFvy3PcChiMCFx9+iTww4bMkQ="; };
          aarch64-darwin = { asset = "apm-darwin-arm64.tar.gz";  sha256 = "sha256-i0aWO/iB0TacHuMPYJn7pU0TN5qIYOwZDNyvUM9Fhqk="; };
          x86_64-darwin  = { asset = "apm-darwin-x86_64.tar.gz"; sha256 = "sha256-ixxDVDETVQ5Jk5x5cEKeGYgdY0fJDEQYXrVepz0OynM="; };
        };
        # rtk 0.43.0 -- tag v0.43.0. Bare single binary `rtk` at root.
        rtk = {
          aarch64-linux  = { asset = "rtk-aarch64-unknown-linux-gnu.tar.gz";  sha256 = "sha256-VRn3yhLlwUOmCfDSigp3uXQTqNzjHCaB8aQcJFGahzE="; };
          x86_64-linux   = { asset = "rtk-x86_64-unknown-linux-musl.tar.gz";  sha256 = "sha256-/4oed2ZJbhdSkaha7KHcl8n/bfM+UeWJPR+8eP6ipgk="; };
          aarch64-darwin = { asset = "rtk-aarch64-apple-darwin.tar.gz";       sha256 = "sha256-ihfkmsvTeJl+sh0Otvf4YREfNbT8mxx07fTHRI5XbGU="; };
          x86_64-darwin  = { asset = "rtk-x86_64-apple-darwin.tar.gz";        sha256 = "sha256-qF9g4mN4Eb5oNmIIuNi5xbobdIy130R3qyDNc9PF2fg="; };
        };
        # betterleaks 1.6.1 -- tag v1.6.1. Bare binary `betterleaks` at root,
        # beside LICENSE/README.md (installPhase installs only the binary).
        betterleaks = {
          aarch64-linux  = { asset = "betterleaks_1.6.1_linux_arm64.tar.gz";  sha256 = "sha256-urloi6loJkrOZ7YI/Hp9j15hIYzecAKdMsvIlOOAj98="; };
          x86_64-linux   = { asset = "betterleaks_1.6.1_linux_x64.tar.gz";    sha256 = "sha256-++/HAKC9RSLMlS3SqPJZzbgFJtfmARSsoZuy1v3ID4E="; };
          aarch64-darwin = { asset = "betterleaks_1.6.1_darwin_arm64.tar.gz"; sha256 = "sha256-mZa/zJP9KuaXbHkC47IXd2bsGWDB4woVOYYJ1Rd+8/g="; };
          x86_64-darwin  = { asset = "betterleaks_1.6.1_darwin_x64.tar.gz";   sha256 = "sha256-B924XEssVdprZxpq9mfInYnGjFKv+P1zoRGKktNz24w="; };
        };
      };

      ghRelease = owner: repo: tag: asset:
        "https://github.com/${owner}/${repo}/releases/download/${tag}/${asset}";

      mkClassB = pkgs:
        let
          sys = pkgs.stdenv.hostPlatform.system;
          d = classBData;
        in
        {
          apm = mkReleaseBinary pkgs {
            pname = "apm";
            version = "0.25.0";
            kind = "wrapperDir";
            url = ghRelease "microsoft" "apm" "v0.25.0" d.apm.${sys}.asset;
            sha256 = d.apm.${sys}.sha256;
          };
          rtk = mkReleaseBinary pkgs {
            pname = "rtk";
            version = "0.43.0";
            kind = "binary";
            url = ghRelease "rtk-ai" "rtk" "v0.43.0" d.rtk.${sys}.asset;
            sha256 = d.rtk.${sys}.sha256;
          };
          betterleaks = mkReleaseBinary pkgs {
            pname = "betterleaks";
            version = "1.6.1";
            kind = "binary";
            url = ghRelease "betterleaks" "betterleaks" "v1.6.1" d.betterleaks.${sys}.asset;
            sha256 = d.betterleaks.${sys}.sha256;
          };
        };

      # Evaluate nixpkgs + the Class B set once per system; both outputs reuse it.
      perSystem = forAllSystems (system:
        let pkgs = import nixpkgs { inherit system; };
        in { inherit pkgs; classB = mkClassB pkgs; });
    in
    {
      packages = forAllSystems (system:
        let inherit (perSystem.${system}) classB; in {
          inherit (classB) apm rtk betterleaks;
        });

      devShells = forAllSystems (system:
        let inherit (perSystem.${system}) pkgs classB; in {
          default = pkgs.mkShellNoCC {
            packages = [
              pkgs.uv
              pkgs.gh
              pkgs.actionlint
              # Class A, deliberately: the pinned nixpkgs input carries
              # zizmor, so no SHA-pin table entry is needed beside
              # betterleaks'. Paired with actionlint rather than standing
              # alone -- skills/scanning-ci-workflows runs both, and each
              # catches what the other does not.
              pkgs.zizmor
              pkgs.python312
              pkgs.bun
              pkgs.lychee
            ] ++ (with classB; [ apm rtk betterleaks ]);

            # Issue #725: `prek` is a pinned dev dependency
            # (pyproject.toml) but installs no git hook by itself --
            # `prek install` must actually run once per clone for
            # .pre-commit-config.yaml to take effect. Running it here
            # covers the devShell entry path documented in
            # CONTRIBUTING.md automatically; `prek install` is
            # idempotent, so re-entering the shell is a no-op once
            # installed. Only run inside a real git checkout (a `nix
            # develop` invoked outside one, e.g. in a template eval,
            # would otherwise fail this hook).
            #
            # Issue #890: both shims are named explicitly. `prek install`
            # with no -t installs the pre-commit shim only, so the
            # betterleaks pre-push hook -- the backstop for a commit that
            # skipped pre-commit via --no-verify -- would silently never
            # run for anyone entering through the devShell.
            #
            # Failures are surfaced, not suppressed. A prior
            # `2>/dev/null || true` here could leave both shims uninstalled
            # while CONTRIBUTING.md told the contributor they were installed
            # automatically -- a false belief that the secret scan is
            # protecting them, which is the same fail-open class #890's own
            # wrapper exists to prevent.
            #
            # Deliberately still non-fatal: a shellHook that exits non-zero
            # breaks `nix develop` outright, locking a contributor out of the
            # whole toolchain over a hook-install hiccup. That is a worse
            # failure than the one being fixed, and the defect here was the
            # silence, not the non-fatality. So it warns loudly and verifies
            # both shims actually landed rather than trusting the exit code.
            # Repository discovery via `git rev-parse`, not a `[ -d .git ]`
            # test. That test is false from any subdirectory, and false inside
            # a linked worktree where `.git` is a file rather than a directory
            # -- so it skipped installation silently in exactly the worktree
            # layout this repository's own agent tooling creates (see
            # .gitignore's /.claude/worktrees/ entry). Both cases were
            # reproduced before this was rewritten. `--show-toplevel` still
            # preserves the original intent of the guard it replaces: it fails
            # outside a checkout, so a `nix develop` in a template eval is
            # still a no-op rather than an error.
            #
            # Hook verification goes through `git rev-parse --git-path hooks`
            # for the same class of reason: it honours core.hooksPath and
            # resolves to the shared common dir from a linked worktree, while
            # a hard-coded `.git/hooks` does neither. It returns a path
            # relative to the toplevel in a normal checkout and an absolute
            # one in a worktree, hence the normalisation. `-x` rather than
            # `-f`: a shim that is not executable never runs.
            # A linked worktree must NOT install. Its hooks directory is the
            # main checkout's shared one, and prek bakes an absolute path to
            # the *installing* tree's .venv/bin/prek into the shim -- so
            # installing from a worktree silently repoints the main checkout's
            # hooks at that worktree's venv, and they break outright once the
            # worktree is removed ("exec: prek: not found"). Reproduced the
            # hard way while testing this very hook. Linked worktrees are
            # routine here (.gitignore's /.claude/worktrees/), so a worktree
            # verifies the shared shims and points at the main checkout
            # instead of writing to them.
            shellHook = ''
              # An executable bit does not prove a shim runs. prek bakes an
              # absolute path to the *installing* tree's .venv/bin/prek into
              # each shim and falls back to a bare `prek` on PATH. A shim left
              # behind by a removed worktree is therefore executable, has a
              # dangling target, and has no fallback -- it dies at `exec` with
              # "prek: not found". Reproduced in an isolated clone: both shims
              # pass -x while the hook does not run at all. So a shim counts as
              # working only if its own target is executable, or `prek` is
              # genuinely on PATH to catch the fallback.
              prek_shim_broken() {
                [ -x "$1" ] || return 0
                target=$(sed -n 's/^PREK="\(.*\)"$/\1/p' "$1" | head -1)
                if [ -n "$target" ] && [ -x "$target" ]; then return 1; fi
                command -v prek >/dev/null 2>&1 && return 1
                return 0
              }
              if root=$(git rev-parse --show-toplevel 2>/dev/null); then
                hooks=$(cd "$root" && git rev-parse --git-path hooks)
                case "$hooks" in
                  /*) ;;
                  *) hooks="$root/$hooks" ;;
                esac
                if [ "$(cd "$root" && git rev-parse --git-dir)" != "$(cd "$root" && git rev-parse --git-common-dir)" ]; then
                  if prek_shim_broken "$hooks/pre-commit" || prek_shim_broken "$hooks/pre-push"; then
                    echo "WARNING: git hooks in the shared hooks directory are missing or unusable:" >&2
                    echo "         $hooks" >&2
                    echo "         This is a linked worktree, which must not install them itself." >&2
                    echo "         Run this in the main checkout: uv run prek install --overwrite -t pre-commit -t pre-push -t commit-msg" >&2
                  fi
                elif ! (cd "$root" && uv run prek install --quiet -t pre-commit -t pre-push -t commit-msg); then
                  echo "WARNING: prek install failed -- git hooks are NOT active." >&2
                  echo "         Fix it with: uv run prek install -t pre-commit -t pre-push -t commit-msg" >&2
                else
                  if prek_shim_broken "$hooks/pre-commit"; then
                    echo "WARNING: $hooks/pre-commit is missing or unusable." >&2
                  fi
                  if prek_shim_broken "$hooks/pre-push"; then
                    echo "WARNING: $hooks/pre-push is missing or unusable -- the betterleaks full-history scan will not run on push." >&2
                  fi
                fi
              fi
            '';
          };
        });
    };
}
