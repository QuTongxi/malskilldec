# CodeQL working directory

- `codeql/`    the CodeQL CLI bundle (not in git).  Install with:

      curl -sSL -o bundle.tar.gz \
        https://github.com/github/codeql-action/releases/download/codeql-bundle-v2.26.2/codeql-bundle-linux64.tar.gz
      tar xzf bundle.tar.gz && rm bundle.tar.gz

- `queries/`   the malicious-skill query pack (python + javascript/typescript).
- `databases/` databases built by `run.sh` (rebuilt on every run).
- `run.sh`     `run.sh <source-root> <output-dir>` -> `<output-dir>/{python,javascript}.sarif`

Query ids are mapped to a behaviour group and a level in `../matchers.py`
(`CODEQL_RULES`).
