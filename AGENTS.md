# TaskArchive contributor contract

- Before every update read the latest default-branch `ARCHIVE_RULES.md` (content policy) and `CONTRIBUTING.md` (current schema and migration limits). User instructions take precedence.
- Target hierarchy: LLM-inferred categories → named projects/topics with description and record span → semantically merged requirements → referenced original user messages with timestamps and provenance.
- Categories are user-dependent, not a universal whitelist. A conversation is not necessarily one requirement. Repeated follow-ups and fixes to the same issue belong to one requirement.
- Preserve original source data. Filtering or folding the display is not authorization to delete user messages. Never fabricate source text, timestamps, status or history coverage.
- Only record real user requests, meaningful constraints and feedback; exclude tool/system/agent/internal execution material from requirements.
- `data/codex.json` belongs to the local Codex collector. Other platforms only update their own stable file in `data/contributions/`.
- Reuse stable IDs and shared project aliases. Update records in place; preserve other platforms' contributions and user corrections. No force pushes or history rewrites.
- The public view is v2, compiled from unchanged legacy snapshots plus data/organized_sources/*.json and the LLM-reviewed data/organized_catalog.json. Follow CONTRIBUTING.md; do not replace other platforms' snapshots or regenerate semantic summaries with keywords.
- For legacy task titles, summarize all relevant user messages. Update reviewed summaries in `data/curation.json` when source messages change; never use just the first message as the display title.
- Run `python3 scripts/build.py` and the repository tests before pushing. Commit generated root `index.html` only if it changes. Never hand-edit generated output or replace the unified entry with a platform-only page.
- Never commit credentials, authentication exports or local databases.

- When organizing knowledge (including image or document interpretation), read `KNOWLEDGE_RULES.md` and respect its image and privacy requirements.
