# Ground Rules — Retro Recaps

Binding rules for this repository. Takes precedence over the global
`~/.claude/CLAUDE.md` wherever the two disagree.

## Session start

Run this procedure before answering the first question of a session:

1. Activate the `caveman` skill (compressed communication mode).
2. Read this file.
3. Read `docs/input/HANDOVER_retro_recap_BOM.md` — the source brief for the project.
4. Read `docs/STATUS.md` if it exists, plus any doc relevant to the task.
5. Load and activate every skill found under `.claude/skills/` (announce each).

## Language

- **Dialogue / chat:** Danish. Technical terms and code identifiers stay in their
  original form (English).
- **Everything written to the repo:** English. This covers markdown, source code,
  comments, commit messages, examples, issue and PR text, and documentation.

## Transcribing

Enabled. Every session is transcribed to `docs/chats/<YYYY-MM-DD>.md` — one file
per date, appended to during the session. The log holds the user's prompts and
the factual substance of the responses.

Exception to the English rule: prompts are recorded verbatim, so the transcript
stays in whatever language the dialogue was held in.

## Execution style

- Prefer subagents where the work allows it. Make them self-contained so they do
  not need follow-up input.
- Collect any input a subagent needs up front, via a `superpowers:brainstorming`
  session, before dispatching it.
- When a plan or skill offers a choice between subagent-driven and inline
  execution, choose subagent-driven without asking. Ask only when
  subagent-driven execution is genuinely not possible.

## Permissions

Reversible, non-destructive operations inside this repository and its
subdirectories may be performed without confirmation — reading, editing,
creating, and running files or builds. Compound commands are fine under the
same constraint.

Always ask first for operations that are destructive or irreversible:

- deleting files or directories
- `git reset --hard`, force push, or other destructive git operations
- flashing or uploading to hardware, overwriting firmware without a backup
- any change outside this working directory and its subdirectories

## Repository facts

- Public repository.
- Documentation lives in `docs/`. Raw source material lives in `docs/input/`
  and is treated as read-only input, not as project output.
- Stack and architecture are not yet decided; do not assume one.

## Amending these rules

When the user changes a standing rule during a session, record it here as a
bullet under the relevant section in the same turn.
