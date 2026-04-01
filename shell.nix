let
  pkgs = import <nixpkgs> {};
in pkgs.mkShell {
  buildInputs = [
    (pkgs.python3.withPackages (python-pkgs: [
      python-pkgs.pandas
      python-pkgs.matplotlib
      python-pkgs.numpy
      python-pkgs.scipy
      python-pkgs.scikit-learn
    ]))
  ];
}
