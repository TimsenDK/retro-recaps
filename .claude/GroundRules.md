# Ground Rules — Retro Recaps

Binding rules for this repository. Takes precedence over the global
`~/.claude/CLAUDE.md` wherever the two disagree.

## Session start

Run this procedure before answering the first question of a session:

1. Activate the `caveman` skill (compressed communication mode).
2. Read this file.
3. Read `<private>/docs/input/HANDOVER_retro_recap_BOM.md` — the source brief for
   the project. See "The private repository" below for what `<private>` means.
4. Read `<private>/docs/STATUS.md` if it exists, plus any doc relevant to the task.
5. Load and activate every skill found under `.claude/skills/` (announce each).

## Language

- **Dialogue / chat:** Danish. Technical terms and code identifiers stay in their
  original form (English).
- **Everything written to the repo:** English. This covers markdown, source code,
  comments, commit messages, examples, issue and PR text, and documentation.

## Transcribing

Enabled. Every session is transcribed to `<private>/docs/chats/<YYYY-MM-DD>.md` —
one file per date, appended to during the session. The log holds the user's prompts and
the factual substance of the responses.

Exception to the English rule: prompts are recorded verbatim, so the transcript
stays in whatever language the dialogue was held in.

**The transcript is shared with the private repository.** A session held there
appends to the same dated file, because a day's work crosses between the two and
splitting it would make neither half readable. Mark every switch of repository
with a heading — `## Continued in the private repository` or `## Continued in the
public repository` — so a reader can tell which checkout a path is relative to.
Unmarked entries are from wherever the file last said.

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
- **The working notes live in a second, private repository.** `docs/` moved out
  of this repository on 2026-08-18; see "The private repository" below. Nothing
  in this repository may link to a `docs/` path — the link would be broken for
  everyone but us, and the directory is not here any more.
- Raw source material lives in `<private>/docs/input/` and is read-only input,
  not project output.
- **Picture sources and the scripts that process them live in `<private>` too**
  (`photo-cache/`, `imagetools/`), since 2026-08-18. Only the finished JPEGs
  under `site/assets/img/machines/` are here. Regenerating a machine picture
  means running `python -m imagetools.cartoonify` from the private checkout; it
  writes into this repository and reads the machine list from `images.yaml`
  here. Nothing in this repository may name those paths.
- **The handover is a lead, not an authority.** `docs/input/HANDOVER_retro_recap_BOM.md`
  and the spreadsheet beside it were an exploratory clarification written before
  this repository existed. They say where someone once looked; they do not say
  what is true. A value resting only on them is `derived` at best, never
  `verified`, however confident the handover sounds — and where it disagrees
  with a source that was actually retrieved, the retrieved source wins. The
  handover is never cited in `sources:` and never named in a note. Establishing
  these values independently is the reason this repository exists.
- Stack: YAML data validated by JSON Schema, Python tooling under `tools/`,
  Jinja2 to static HTML, GitHub Pages. Data under `data/` and `reference/`.
- Licensing is split: code MIT, data and documentation CC BY-SA 4.0.

## What belongs in a YAML note

A `note` in `data/` states a fact about the board or the position, and nothing
else. Physical constraints, what a revision differs on, which variant a list
describes, that a value is unconfirmed. Present tense, about the hardware.

Three things never go in a note:

- **Citations.** The `sources:` block is where a source belongs. A note must not
  name a site, quote one, or say which source a value came from.
- **Provenance narrative.** How a value was arrived at, which source disagreed
  with which, what the spreadsheet said — that is research history, not a fact
  about the board.
- **Our own corrections.** A note never records that this project previously had
  something wrong. The reader is recapping a board; our earlier mistakes are
  noise to them, and a dataset that narrates its own history reads as unsure of
  itself.

All three belong in `<private>/docs/NOTES.md` — provenance, disagreements
between sources, and corrections — with the exact retrieved URLs in
`<private>/docs/SOURCES.md`. Both are private, so they can be as candid as they
need to be.

The test: would this sentence still be worth reading to someone holding the
board, who has never heard of this project? If not, it goes in the private
repository's `docs/`.

## The private repository

`<private>` is `E:/repos/retro-recaps-private`, a separate git repository, and
reading and updating it is permitted without asking. It holds `docs/` — specs,
implementation plans, session transcripts, `NOTES.md`, `SOURCES.md`, `TODO.md`
and the source material the project was seeded from.

- Written output there follows the same English rule as everything else.
- The two repositories are committed separately. Work in one never commits in
  the other.
- This repository is public and that one is not: anything candid — provenance,
  disagreements between sources, our own corrections, half-formed plans —
  belongs there, and nothing here may point at it by path.

## Amending these rules

When the user changes a standing rule during a session, record it here as a
bullet under the relevant section in the same turn.
