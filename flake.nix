{
  description = "gitapex external toolchain (SSoT for uv/gh/actionlint/python/bun/lychee + waza/apm/rtk/betterleaks)";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { nixpkgs, ... }:
    let
      systems = [ "aarch64-linux" "x86_64-linux" "aarch64-darwin" "x86_64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;

      # --- Class B: SHA-pinned prebuilt release binaries (static, regex-parseable) ---
      # mkReleaseBin-style helper: each tool fetches one asset per system and
      # installs a single binary. installPhase is per-tool because archive
      # layouts differ (see docs/superpowers/notes/2026-07-14-pr1-spikes.md).
      mkClassB = pkgs:
        let
          fetch = url: sha256: pkgs.fetchurl { inherit url sha256; };

          # waza 0.38.0 -- tag azd-ext-microsoft-azd-waza_0.38.0
          # LINUX assets are bare .tar.gz with the exec bit preserved.
          # DARWIN assets are bare .ZIP (not .tar.gz); the zip does not
          # preserve the unix exec bit, so installPhase below sets it
          # explicitly via `install -Dm755`. Binary filename = asset
          # basename without extension. There is also an extension.yaml
          # at root (azd extension manifest, ignored here).
          wazaAsset = {
            aarch64-linux = "microsoft-azd-waza-linux-arm64.tar.gz";
            x86_64-linux = "microsoft-azd-waza-linux-amd64.tar.gz";
            aarch64-darwin = "microsoft-azd-waza-darwin-arm64.zip";
            x86_64-darwin = "microsoft-azd-waza-darwin-amd64.zip";
          };
          wazaBin = {
            aarch64-linux = "microsoft-azd-waza-linux-arm64";
            x86_64-linux = "microsoft-azd-waza-linux-amd64";
            aarch64-darwin = "microsoft-azd-waza-darwin-arm64";
            x86_64-darwin = "microsoft-azd-waza-darwin-amd64";
          };
          wazaSha = {
            aarch64-linux = "sha256-mMvXJj4SWp0eHmePe1oiPxkNK8WHgdtO9vr+1dtca8Y=";
            x86_64-linux = "sha256-wTSCyGVSPVkBaLBCoLLtGh6f02O+ZQPt7GWaR0Np6Dk=";
            aarch64-darwin = "sha256-EemENS67eo03UpMVT63qPvFUenS0WqT0KO9IiUqf/G4=";
            x86_64-darwin = "sha256-Os9aVBbvRjgZaH0hN50lhXFEmCf0UmJjl4NafcBeX+0=";
          };

          # apm 0.25.0 -- tag v0.25.0
          # Each asset unpacks to a single top-level directory
          # apm-<os>-<arch>/ containing `apm` (a thin PyInstaller loader)
          # and `_internal/` (~157 entries) which MUST sit beside `apm`
          # at runtime. Nix's default unpackPhase auto-descends into that
          # sole top-level directory, so no sourceRoot override is needed
          # here (unlike waza/rtk/betterleaks below).
          apmAsset = {
            aarch64-linux = "apm-linux-arm64.tar.gz";
            x86_64-linux = "apm-linux-x86_64.tar.gz";
            aarch64-darwin = "apm-darwin-arm64.tar.gz";
            x86_64-darwin = "apm-darwin-x86_64.tar.gz";
          };
          apmSha = {
            aarch64-linux = "sha256-li0NRjVEvbpC8smejaoS7vKr0V1S4Yv7utB/sT5XMwU=";
            x86_64-linux = "sha256-ekKB75Felgn4hB7O0ZKFvy3PcChiMCFx9+iTww4bMkQ=";
            aarch64-darwin = "sha256-i0aWO/iB0TacHuMPYJn7pU0TN5qIYOwZDNyvUM9Fhqk=";
            x86_64-darwin = "sha256-ixxDVDETVQ5Jk5x5cEKeGYgdY0fJDEQYXrVepz0OynM=";
          };

          # rtk 0.43.0 -- tag v0.43.0
          # Bare single binary `rtk` at archive root -> sourceRoot = ".".
          rtkAsset = {
            aarch64-linux = "rtk-aarch64-unknown-linux-gnu.tar.gz";
            x86_64-linux = "rtk-x86_64-unknown-linux-musl.tar.gz";
            aarch64-darwin = "rtk-aarch64-apple-darwin.tar.gz";
            x86_64-darwin = "rtk-x86_64-apple-darwin.tar.gz";
          };
          rtkSha = {
            aarch64-linux = "sha256-VRn3yhLlwUOmCfDSigp3uXQTqNzjHCaB8aQcJFGahzE=";
            x86_64-linux = "sha256-/4oed2ZJbhdSkaha7KHcl8n/bfM+UeWJPR+8eP6ipgk=";
            aarch64-darwin = "sha256-ihfkmsvTeJl+sh0Otvf4YREfNbT8mxx07fTHRI5XbGU=";
            x86_64-darwin = "sha256-qF9g4mN4Eb5oNmIIuNi5xbobdIy130R3qyDNc9PF2fg=";
          };

          # betterleaks 1.6.1 -- tag v1.6.1
          # Bare archive, but LICENSE/README.md are also present at root
          # alongside the binary -> install only the `betterleaks` binary,
          # sourceRoot = ".".
          betterleaksAsset = {
            aarch64-linux = "betterleaks_1.6.1_linux_arm64.tar.gz";
            x86_64-linux = "betterleaks_1.6.1_linux_x64.tar.gz";
            aarch64-darwin = "betterleaks_1.6.1_darwin_arm64.tar.gz";
            x86_64-darwin = "betterleaks_1.6.1_darwin_x64.tar.gz";
          };
          betterleaksSha = {
            aarch64-linux = "sha256-urloi6loJkrOZ7YI/Hp9j15hIYzecAKdMsvIlOOAj98=";
            x86_64-linux = "sha256-++/HAKC9RSLMlS3SqPJZzbgFJtfmARSsoZuy1v3ID4E=";
            aarch64-darwin = "sha256-mZa/zJP9KuaXbHkC47IXd2bsGWDB4woVOYYJ1Rd+8/g=";
            x86_64-darwin = "sha256-B924XEssVdprZxpq9mfInYnGjFKv+P1zoRGKktNz24w=";
          };
        in
        {
          waza = pkgs.stdenvNoCC.mkDerivation {
            pname = "waza";
            version = "0.38.0";
            src = fetch
              "https://github.com/microsoft/waza/releases/download/azd-ext-microsoft-azd-waza_0.38.0/${wazaAsset.${pkgs.system}}"
              wazaSha.${pkgs.system};
            nativeBuildInputs = [ pkgs.unzip ];
            sourceRoot = ".";
            dontBuild = true;
            dontStrip = true;
            dontPatchELF = true;
            installPhase = ''
              runHook preInstall
              install -Dm755 ${wazaBin.${pkgs.system}} $out/bin/waza
              runHook postInstall
            '';
          };

          apm = pkgs.stdenvNoCC.mkDerivation {
            pname = "apm";
            version = "0.25.0";
            src = fetch
              "https://github.com/microsoft/apm/releases/download/v0.25.0/${apmAsset.${pkgs.system}}"
              apmSha.${pkgs.system};
            nativeBuildInputs = [ pkgs.makeWrapper ];
            dontBuild = true;
            dontStrip = true;
            dontPatchELF = true;
            installPhase = ''
              runHook preInstall
              mkdir -p $out/libexec/apm
              cp -r . $out/libexec/apm/
              chmod +x $out/libexec/apm/apm
              makeWrapper $out/libexec/apm/apm $out/bin/apm
              runHook postInstall
            '';
          };

          rtk = pkgs.stdenvNoCC.mkDerivation {
            pname = "rtk";
            version = "0.43.0";
            src = fetch
              "https://github.com/rtk-ai/rtk/releases/download/v0.43.0/${rtkAsset.${pkgs.system}}"
              rtkSha.${pkgs.system};
            sourceRoot = ".";
            dontBuild = true;
            dontStrip = true;
            dontPatchELF = true;
            installPhase = ''
              runHook preInstall
              install -Dm755 rtk $out/bin/rtk
              runHook postInstall
            '';
          };

          betterleaks = pkgs.stdenvNoCC.mkDerivation {
            pname = "betterleaks";
            version = "1.6.1";
            src = fetch
              "https://github.com/betterleaks/betterleaks/releases/download/v1.6.1/${betterleaksAsset.${pkgs.system}}"
              betterleaksSha.${pkgs.system};
            sourceRoot = ".";
            dontBuild = true;
            dontStrip = true;
            dontPatchELF = true;
            installPhase = ''
              runHook preInstall
              install -Dm755 betterleaks $out/bin/betterleaks
              runHook postInstall
            '';
          };
        };
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          b = mkClassB pkgs;
        in
        { inherit (b) waza apm rtk betterleaks; });

      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          b = mkClassB pkgs;
        in
        {
          default = pkgs.mkShellNoCC {
            packages = [
              pkgs.uv
              pkgs.gh
              pkgs.actionlint
              pkgs.python312
              pkgs.bun
              pkgs.lychee
              b.waza
              b.apm
              b.rtk
              b.betterleaks
            ];
          };
        });
    };
}
