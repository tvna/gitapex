{
  description = "gitapex external toolchain (SSoT for uv/gh/actionlint/python/bun/lychee + waza/apm/rtk/betterleaks)";

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
        # waza 0.38.0 -- tag azd-ext-microsoft-azd-waza_0.38.0. Linux assets
        # are bare .tar.gz (exec bit preserved); darwin assets are bare .zip
        # (exec bit dropped -> install -Dm755 restores it). Binary name = asset
        # basename without extension; an extension.yaml at root is ignored.
        waza = {
          aarch64-linux  = { asset = "microsoft-azd-waza-linux-arm64.tar.gz";  bin = "microsoft-azd-waza-linux-arm64";  sha256 = "sha256-mMvXJj4SWp0eHmePe1oiPxkNK8WHgdtO9vr+1dtca8Y="; };
          x86_64-linux   = { asset = "microsoft-azd-waza-linux-amd64.tar.gz";  bin = "microsoft-azd-waza-linux-amd64";  sha256 = "sha256-wTSCyGVSPVkBaLBCoLLtGh6f02O+ZQPt7GWaR0Np6Dk="; };
          aarch64-darwin = { asset = "microsoft-azd-waza-darwin-arm64.zip";    bin = "microsoft-azd-waza-darwin-arm64"; sha256 = "sha256-EemENS67eo03UpMVT63qPvFUenS0WqT0KO9IiUqf/G4="; };
          x86_64-darwin  = { asset = "microsoft-azd-waza-darwin-amd64.zip";    bin = "microsoft-azd-waza-darwin-amd64"; sha256 = "sha256-Os9aVBbvRjgZaH0hN50lhXFEmCf0UmJjl4NafcBeX+0="; };
        };
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
          waza = mkReleaseBinary pkgs {
            pname = "waza";
            version = "0.38.0";
            kind = "binary";
            url = ghRelease "microsoft" "waza" "azd-ext-microsoft-azd-waza_0.38.0" d.waza.${sys}.asset;
            sha256 = d.waza.${sys}.sha256;
            binInArchive = d.waza.${sys}.bin;
          };
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
          inherit (classB) waza apm rtk betterleaks;
        });

      devShells = forAllSystems (system:
        let inherit (perSystem.${system}) pkgs classB; in {
          default = pkgs.mkShellNoCC {
            packages = [
              pkgs.uv
              pkgs.gh
              pkgs.actionlint
              pkgs.python312
              pkgs.bun
              pkgs.lychee
            ] ++ (with classB; [ waza apm rtk betterleaks ]);

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
            shellHook = ''
              if [ -d .git ]; then
                uv run prek install --quiet 2>/dev/null || true
              fi
            '';
          };
        });
    };
}
