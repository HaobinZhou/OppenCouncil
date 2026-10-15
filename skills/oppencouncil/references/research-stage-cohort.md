# Cohort construction

`index TARGET` lists current owners, role paths and registered outputs. Read a registered F with `python -m oppencouncil definition TARGET --question F-NNNNNN`.

The output registration kind for a cohort flow is `cohort-flow`. `result TARGET --input FILE` binds its path, audience, numbered producer and exact confirmed output specification. Generated cohort datasets use `data register` with kind `derived`. Payloads and verification registration are in [project-operations.md](project-operations.md); proposed specification changes use [review-packet.md](review-packet.md).

`validate TARGET` checks these registrations and paths. The cohort's executable checks test its actual inclusion, exclusion and counting rules.
