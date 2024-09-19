{
  description = "Screen blanking and locking manager";

  inputs = {
    nixpkgs.url = "nixpkgs/bff917a3ed37b1f9e705b5c07210acd295691770";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
      	pkgs = import nixpkgs { inherit system; };
      in {
        packages.default = pkgs.stdenv.mkDerivation {
          name = "blankie";
          src = ./src;
          nativeBuildInputs = [
            pkgs.makeWrapper
          ];
          installPhase = ''
            runHook preInstall
            mkdir -p $out/bin $out/lib
            cp -r $src/blankie $out/lib/blankie
            makeWrapper \
              ${pkgs.python3}/bin/python \
              $out/bin/blankie \
              --prefix PATH : ${pkgs.lib.makeBinPath [
                # not included:
                # - physlock, as it must be suid-root
                # - i3lock, as it must be installed alongside its PAM module
                pkgs.dunst
                pkgs.procps
                pkgs.systemd
                pkgs.upower
                pkgs.xorg.setxkbmap
                pkgs.xorg.xset
                pkgs.acpilight
                pkgs.xprintidle
              ]} \
              --set PYTHONPATH $out/lib:${pkgs.python3Packages.makePythonPath [
                pkgs.python3Packages.dbus-python
                pkgs.python3Packages.inotify-simple
                pkgs.python3Packages.pygobject3
                pkgs.python3Packages.xlib
              ]} \
              --add-flags "-m blankie"
            runHook postInstall
          '';
        };

        # An app that uses the `runme` package
        apps.default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/blankie";
        };
      });
}
