# deadcode

Python static analyzer based on AST. Finds unused functions, classes, variables, and imports.

## Usage

```bash
pip install deadcode
deadcode .
deadcode . --ignore "test_*" --format json
```

## What it does NOT do

No code execution, no dynamic analysis. Use alongside mypy and ruff for full coverage.
