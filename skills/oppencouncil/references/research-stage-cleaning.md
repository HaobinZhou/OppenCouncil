# Data import and cleaning

The declared project type and registered paths come from `index TARGET`; this stage applies independently of language. `data register TARGET --input FILE` registers an existing file without moving it. Payloads:

```json
{"path":"Data/raw/input.csv","kind":"raw","version":"source-version","source":"Actual input provenance"}
```

```json
{"path":"Data/derived/cleaned.csv","kind":"derived","version":"generation-version","producer":"Scripts/01_clean.py"}
```

The helper calculates size and hash. `validate TARGET` checks classification, registered paths and script naming; data correctness comes from the project's executable checks. A research audit completion payload has `summary`, `checks` (paths), `verification` and `limits`; creation/completion commands and current evidence-tree replacement are in [project-operations.md](project-operations.md).
