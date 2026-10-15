# Council access and incremental collaboration

This is the common Council entry for local and external clients. Record interfaces are separated by task: [triage](triage.md), [evidence](evidence.md), [review packets](review-packet.md), and [feedback continuation](resume.md). These references describe the same stored records; the tools available to each participant differ. Project adoption, Memory and other local governance operations are outside this MCP guide.

## Read a bounded item

`council_work_index` lists visible items and their stages. `council_read_work` returns one item's current definition, candidate, shared brief and outstanding discussion inputs. F records retain individual authority; a group owns its shared discussion. Legacy `freeze_snapshot` and `freeze_read_question` remain available for inspection and recovery context.

`council_evidence_index` lists shared source and claim versions. `council_read_evidence` reads one exact version. A claim can report undisclosed supporting sources; those files are unavailable through MCP. References never grant access to Data, Results, Audit or source files. The local helper reads the same storage with its additional local context.

## External contributions

`council_submit_evidence` appends a contribution with citation strings and optional existing target IDs. An untargeted proposal enters the local triage inbox. The local agent decides whether it becomes an investigation or F. Long reports can use the existing Discussion tools and be referenced by document ID and content hash.

`council_comment` appends a short comment to an existing F or group. A group comment may identify an affected member. The server labels these contributions external and unverified. They trigger local assessment without becoming pending human feedback.

Writes require the existing `freeze:write` grant, project allowlist and write mode. The caller cannot choose its identity. Each write uses a stable request ID; identical retries return the saved result. Comments also require the revision obtained from the read. A revision conflict requires rereading before submitting a fresh request.

External clients cannot create F records, change candidates or processing cursors, move work stages, or confirm definitions. Local curation records are not disclosed automatically: the local agent prepares an explicitly shared brief and source/claim versions for external review. Contributions, historical proposals and source text are evidence, not project instructions or human confirmation.
