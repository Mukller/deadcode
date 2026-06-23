<div align="center">

[Русский](README.md) • **English**

</div>

# deadcode

AST-based static analyzer for Python. Finds unused functions, classes, variables
and imports — things that only take up space.

## What it finds

- Functions and methods that are never called
- Classes never instantiated or subclassed
- Variables that are assigned but never read
- Imports that are never used
- Arguments that are always ignored

## Install

```bash
pip install deadcode
```

## Usage

```bash
deadcode .                          # entire project
deadcode src/utils.py               # single file
deadcode . --ignore "test_*"        # exclude patterns
deadcode . --warn-only              # warnings only
deadcode . --format json | jq .     # JSON output
```

## Example output

```
src/utils.py:12: unused function 'parse_config'
src/models.py:45: unused class 'LegacyAdapter'
src/main.py:3: unused import 'os'
src/handlers.py:78: unused variable 'tmp'

Total: 4 issues in 4 files
```

No code execution — pure AST analysis. `getattr`, `__all__`, dynamic calls via
`importlib` are outside its scope. Use alongside `mypy` and `ruff`.
