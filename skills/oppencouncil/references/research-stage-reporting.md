# Report assembly

`index TARGET` returns current output registrations and their specification bindings. A table or figure uses its own confirmed specification; an output group supplies `member_specifications` for every member. The [project interface](project-operations.md) describes registration and intended path replacements. Ordinary regeneration at the registered path keeps its binding.

`validate TARGET` checks the current files and registrations. A requested historical package is a separate local [release operation](releases.md), with its own inventory, original-input references and environment record. Existing packages are checked with `release verify TARGET`.
