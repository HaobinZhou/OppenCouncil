# Descriptive analysis

`index TARGET` lists registered tables and their producers. Read their confirmed output specifications with `python -m oppencouncil definition TARGET --question F-NNNNNN`. An existing registration stays in place when its producer regenerates the same output under the same specification.

The output registration kind is `table`. Registration, data and audit payloads are in [project-operations.md](project-operations.md); candidate table formats and saved simulated examples use [output-specifications.md](output-specifications.md). `validate TARGET` checks registered structures; it does not render or interpret a table.
