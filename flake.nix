{
  description = "Blankie - X ScreenSaver / power manager for DIY desktops";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});

      pythonDeps = ps: with ps; [ dbus-python inotify-simple pygobject3 xlib ];

      # Runtime executables invoked via subprocess.
      # NOTE: physlock (must be setuid-root) and i3lock (needs its PAM
      # module installed system-wide) are intentionally NOT included -
      # they must be installed on the host and found on PATH at runtime.
      runtimeDeps = pkgs: with pkgs; [
        dunst procps systemd upower acpilight xprintidle
        setxkbmap xset
      ];
    in
    {
      packages = forAllSystems (pkgs: rec {
        blankie = pkgs.python3Packages.buildPythonApplication {
          pname = "blankie";
          version = "0.1.0";
          src = ./.;
          pyproject = true;

          build-system = [ pkgs.python3Packages.setuptools ];
          dependencies = pythonDeps pkgs.python3Packages;

          nativeBuildInputs = [ pkgs.makeWrapper ];
          makeWrapperArgs = [
            "--prefix PATH : ${pkgs.lib.makeBinPath (runtimeDeps pkgs)}"
          ];
        };
        default = blankie;
      });

      apps = forAllSystems (pkgs: {
        default = {
          type = "app";
          program = "${self.packages.${pkgs.system}.blankie}/bin/blankie";
        };
      });

      # Replaces the old blankie-nix script: run `nix develop` then `./blankie`.
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = [
            (pkgs.python3.withPackages pythonDeps)
          ] ++ runtimeDeps pkgs;
        };
      });
    };
}
