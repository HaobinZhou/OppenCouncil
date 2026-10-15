# Investigation interface

For research projects, first apply [the research handoff](research-handoff.md). Phase labels describe saved work, not permission to finish all phases without returning control to the human.

An investigation has an I ID and can link existing F IDs with `question_ids`. Create or update it through [local-council.md](local-council.md). `work-index` also lists untargeted external submissions awaiting local assessment; external submission alone does not create a human-review item.

The stored conclusion values are `not_applicable`, `fact_lookup`, `covered`, `single_recommendation`, `parallel_recommendations`, `departure`, `tradeoff`, and `needs_check`. The stored work phases are `triage`, `evidence`, `prepare_review`, `human_review`, and `closed`. Each stage change records its reason, affected scope and completion conditions. A closed investigation retains its earlier reasons and can be reopened.

For source versions use [evidence.md](evidence.md); candidate and review-packet fields are in [review-packet.md](review-packet.md).
