{
  description = "ProtonFetcher - Reproducible Python zipapp build environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python313;  # Match .python-version
      in
      {
        devShells.default = pkgs.mkShell {
          name = "protonfetcher";

          buildInputs = [
            python
            pkgs.zip          # Deterministic zip archive creation
            pkgs.rsync        # File copying with exclusion patterns
            pkgs.gnused       # GNU sed for in-place editing
            pkgs.coreutils    # touch, sha256sum, date, etc.
            pkgs.gnutar       # GNU tar (fallback)
          ];

          shellHook = ''
            export PYTHON=${python}/bin/python3

            echo "ProtonFetcher development environment loaded"
            echo "Python: $(python --version)"
            echo ""
            echo "Build with: make build"
            echo "The Makefile sets SOURCE_DATE_EPOCH for reproducible builds"
          '';
        };
      }
    );
}
