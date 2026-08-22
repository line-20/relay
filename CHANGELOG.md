# Changelog

All notable changes to Relay. Versions follow [semver](https://semver.org); the plugin's
version lives in `plugins/relay/.claude-plugin/plugin.json`.

To pick up a new version, colleagues refresh via the `/plugin` manager — `/plugin marketplace
update line-20` then update the `relay` plugin. Their repos' `relay/` folders are their own
data and are never touched by an update.

## 1.18.0 — the poor-man's merge queue

Run ten sessions in parallel and they all race to land on `main`. The moment any one merges, every
other in-flight PR's green run no longer describes the merged result — so `/ship`'s merge gate made
them all rebase and re-run the full suite before merging. Most of those re-runs were wasted: the
sibling's work was in a package the re-running PR never touched. On a capacity-limited CI those wasted
runs queue up and *become* the bottleneck. The real cure is a GitHub merge queue, which a private repo
on the Team plan can't have. This is the substitute — merge optimistically, gated on real overlap,
backstopped by the full-suite run `main` already does after every merge.

**Added**
- **`/ship` skips the re-run when a sibling merge doesn't overlap your PR.** When the base moves after
  your green, the merge gate no longer re-verifies unconditionally — it asks whether what landed
  actually touches your PR's build and tests, and if it's disjoint, merges on the green you already
  have. A sibling landing eight commits in `module-invoicing` no longer stalls your `module-shipping`
  PR behind another full CI run. Safe because `main` runs the full suite after every merge — that
  post-merge run is the real backstop, and the skipped per-PR re-verify was belt-and-braces that
  catches nothing for a genuinely disjoint change. Every other merge condition — blockers resolved,
  mergeable, checks green — is untouched.
- **A new optional `hooks.affects` answers the overlap question.** `/ship` is stack-agnostic and can't
  know what "affected scope" means in your project (a pnpm `--filter` closure, a Cargo workspace, a
  single package), so the project owns the call: given what landed on the base and the PR's own diff,
  the hook reports `disjoint` or `overlap`, and must report `overlap` for anything that invalidates
  *every* package — a repo-root, CI-config or lockfile change, a migration. **No hook configured ⇒
  `/ship` re-verifies unconditionally, exactly as before.** The optimisation is strictly opt-in; a
  wrong `disjoint` is the one failure mode that matters, so Relay never guesses overlap on the
  project's behalf.

## 1.17.0 — the handover hands you the next command

`/handover` ended on a generic nudge — "`/continue` picks this up from main" — which still left
the cold session to work out *which* handover was the latest before it could start. The last thing
you read is now the exact command to run next.

**Changed**
- **`/handover` prints the ready-to-paste continuation line as its final output.** Instead of a
  generic hint, the last line is the literal command the next session runs, carrying this handover's
  real path — e.g. `/rlc relay/handover/next-2026-08-22-0821.md`. `/clear`, paste, and the cold
  session lands on *this* thread with no hunting for which file is the latest. If the handover didn't
  make it to main, the line still prints but tells you to commit it first, so you are never pointed
  at a handover that never shipped. `/ship` inherits this, since it ends by running `/handover`.

## 1.16.0 — mind your own work

Two steps in the loop stopped taking themselves on trust. `/fix` used to apply a review's fixes and
report success on a green suite — but the fix pass is the most defect-dense diff in the loop, and a fix
that quietly breaks a neighbour sails through because the new tests only cover the happy path. And
`/persist` used to hold the whole end-of-lap harvest behind one approval prompt, so the step that banks
lessons was the one most often skipped.

**Added**
- **`/fix` re-reviews its own fixes before reporting green.** After applying a review's fixes, it
  re-reviews just the fix diff with an independent agent — did each finding actually close, and did the
  fix break something next to it? Only a blocker-class problem loops it back (bounded, then handed to
  you); a check that can't run reports **unverified**, never a false green. When the fix touched
  something risky — auth, SQL, a migration, backend data-access — it also pulls in the matching review
  specialist over that diff.

**Changed**
- **`/persist` banks what you steered instead of asking you to approve it.** The end-of-lap harvest no
  longer stops behind one approval prompt. Everything additive — memory notes, release notes, guardrail
  and design-guide additions — writes straight away, and you get a one-line summary of what landed. The
  only pause is when it would drop wording saved nowhere else. Lessons that used to get stranded at the
  approval step now just land.

## 1.15.0 — commit is not a question

`/test` and `/ship` promised to open a PR for you, then stopped short: on an uncommitted tree they
handed the commit back — and "hand it back" has no single shape, so each run improvised. One time a
report, one time instructions for making a PR yourself, one time a "say go" proposal. Now they commit
the slice themselves and carry on, so the step reads the same every time.

**Changed**
- **`/test` and `/ship` commit a dirty tree automatically** as part of ensuring a PR — they author a
  Conventional-Commits message from the actual diff, `git add -A && git commit`, then open the draft
  PR. No more asking you to commit first, no improvised hand-off. In Relay's worktree-per-session
  model the tree *is* the slice under test, so capturing it is the point of the command, not a
  decision to defer. Not ready to commit? **`plan-only`** still touches nothing — that's the escape
  hatch.
- **The dirty-tree safety gate is redrawn around what it actually protects.** *Discarding* or
  overwriting uncommitted work (stash, reset, force-checkout) stays a hard STOP at every autonomy
  level. *Committing* a dirty tree is additive and reversible (a `git reset` undoes it), so it is no
  longer gated — losing work is the thing worth stopping for, not capturing it.

## 1.14.0 — some days you feel like security

The `/next` shortlist told you *which* items to pick up, never *what kind* of work each one is — so if
you woke up with an appetite for security, or for a quick refactor, you had to open each item to find
out. Now the kind is right there in the list.

**Added**
- **A `Tags` column on the `/next` shortlist.** Every shortlisted item carries **one or two** category
  tags from a **fixed vocabulary** — `security` · `hardening` · `privacy` · `feature` · `bug` ·
  `refactor` · `perf` · `docs` — so you can pick by appetite at a glance. Tags are **assigned at
  ranking time** (nothing is stored on the board or a brief) and drawn only from the fixed set, so
  "give me security" matches the same thing every run; the list grows with Relay's vocabulary, not
  per run.
- **Tags are a pick aid, nothing more.** They never change the ranking — that stays the job of the
  1.13.0 maturity lens, kept deliberately separate. A tag never sinks or lifts an item; it just tells
  you what the work is.

## 1.13.0 — good work, wrong week

`/next` ranked by risk and leverage — and never asked *where the product is in its life*. So on a
pre-launch MVP that nobody uses yet, "harden the tenant isolation" out-ranked "build the screen that
wins the next user", because bulletproofing scores high on risk every time. That's the wrong bet while
you're still proving the thing is worth building at all: a week spent making a detail rock-solid on a
product that never ships is a week burned. The fix is one knob that tells `/next` the stage, and lets
it bend the ranking accordingly.

**Added**
- **`/relay:config maturity`** — a single project-wide value in `relay.config.json` (committed truth,
  not a per-driver taste): `mvp` · `growth` · `scale`. It says where the product is, so every session
  ranks the same way. Absent ⇒ nothing changes.
- **`/next` now ranks with a maturity lens.** For each shortlisted item it judges *payoff timing* at the
  set stage — does this make the product more attractive **now** (a feature, the core flow), or pay off
  **later** once there are users, volume, or regulators (hardening, security, privacy, scale
  robustness)? At **`mvp`** the pay-off-later work is **down-weighted** below feature work; at
  **`growth`** they rank evenly; at **`scale`** the hardening/compliance work is **up-weighted**. It
  **only ever re-orders and annotates** — never filters or hides an item, and never overrides a hard
  safety signal (a security hole that's also a live break still earns its bump). A sunk item carries a
  one-line footnote — `↓ deferred-payoff, parked behind MVP features (maturity: mvp)` — so the good work
  is visibly still there, just lower, and you can see why.
- **The project lead moves the needle — never Relay.** `/next` only ever *notices* when the stage looks
  stale ("real users now — still `mvp`?") and suggests re-setting; the change is always a deliberate
  `/relay:config maturity`.

## 1.12.0 — refutation without remembering to ask for it

1.11.0 put refutation behind a word you had to type. That's the wrong shape for a safety net: the
laps where it matters most are the ones where you're moving fast enough not to think about it, and a
protection you have to remember isn't one.

**Changed**
- **Refutation is automatic, and the trigger is a blocker.** `/rls` now refutes every 🔴 the fan-out
  raised, no argument needed. Diff size doesn't predict a misread — a three-line change in
  unfamiliar code misreads as easily as a big one — but a 🔴 is the only finding class that *costs*
  something: it flips the verdict to `request-changes`, triggers a fix pass and holds the merge. Two
  agents to check a claim that's about to stop your lap always pays; a stray 🟡 is a paragraph you
  skim past.
- **A clean review costs exactly nothing.** No blockers ⇒ no refuters launched, no tokens spent, no
  visible difference. That's most laps.
- **`audit` now *widens* rather than switches on** — 🔴 **and** 🟡, the 1.11.0 behaviour. **`no-audit`
  switches the whole step off.** In config, `review.verify` becomes `auto` (default) · `always` ·
  `never`; the booleans 1.11.0 shipped still read as `always`/`never`.

**Added**
- **A STOP gate on the last blocker.** Dropping a 🔴 normally just tidies the report — but dropping
  the *last* one flips the verdict to `approve`, and under `/ship` that is what lets the branch
  merge. Refutation would be deciding what lands, not just what you read. So when the refuted set
  would leave zero blockers, Relay stops and shows you the claim and both refuters' reasons: drop it
  and approve, or keep it and let the fix pass look. Blockers 2..N are still dropped quietly; only
  the merge-deciding one asks. This overrides `autonomy.decide` — a merge gate isn't a routine call.
- **`verified:` now names its scope** — `none` · `blockers` · `all` — so `/fix` and Phase 4 know
  exactly which findings were already attacked and can fast-confirm those while looking at full
  strength at everything else. It replaces 1.11.0's `verified: true|false`, which couldn't say that.

## 1.11.0 — a finding has to survive being wrong

A review specialist reads a diff, and a diff is a fragment. So it reports the missing tenant filter
it can't see, not knowing the filter sits one layer up in a shared repository call. Relay already
knew this — `/fix` opens by re-verifying every finding *as a claim*, and classifies some of them
`wrong` — but by then the finding has been written into the report, read by you, and re-read by the
fix pass. Three touches for something that was never true. And nothing recorded that it happened, so
the same false finding came back the next lap, and the one after that.

**Added**
- **`audit` on `/ship` and `/review` refutes findings before they reach the report.** Between the
  specialists returning and the report being written, every 🔴 and 🟡 gets **two independent
  refuters** — one asking whether the specialist misread the code (reading the whole file, not the
  hunk it saw), one asking whether the concern is already handled somewhere it didn't look. Nits are
  left alone; two agents cost more than a nit. Refuters are told to **keep the finding when
  uncertain**, because dropping a real blocker ships a bug while a noisy one costs a paragraph.
- **A finding dies only on a unanimous verdict.** Both refuters must agree. A split vote keeps the
  finding at its **original severity** and annotates it `(contested: …)` — a blocker never gets
  downgraded, and the verdict never flips, on a one-to-one call.
- **Nothing is dropped silently.** The report grows a fifth always-present section, *Refuted
  findings*, listing every dropped claim with both reasons. It reads `_Not run_` on an ordinary
  lap. This is the section that tells you whether refutation is calibrated or quietly eating real
  bugs — read it deliberately on a new project.
- **`/fix` and `/ship`'s Phase 4 spend less on what already survived.** A report with
  `verified: true` gets a fast confirm on its 🔴/🟡 rather than a full re-read, keeping full strength
  for 🟢, for anything `(contested: …)`, and always for the stale check — code moves after a review,
  which is a different question from whether the claim was true when it was made.
- **`/persist` harvests the refutations too.** A specialist refuted the same way three laps running
  isn't noise; it's an undocumented project rule ("the tenant filter lives in the repository layer,
  not the query"). Writing it into the guardrails is what stops the false finding recurring — the
  loop closes rather than just filtering.

Off by default, and off is the conservative setting: refutation only ever *removes* findings, so a
plain `/rls` behaves exactly as it did in 1.10.1 — same specialists, same report, same cost. Turn it
on per lap with `/rls audit`, or per project with `review.verify: true`. Expect roughly double the
review's tokens when it runs, partly repaid by the cheaper fix pass.

## 1.10.1 — both names, side by side

1.10.0 gave the ten loop commands their short names with a frontmatter `name:` — and a plugin
command's `name:` **replaces** the name its filename gives it rather than adding to it. So the `/`
menu stopped listing `/relay:test`, `/relay:next` and the other eight: typing one in full still ran
it (that part of 1.10.0's note was right), but it was no longer there to be found, picked or
autocompleted. Whoever knew the `rl` mapping lost nothing; everyone else lost the command.

**Fixed**
- **Both names are listed again.** Every loop command keeps its own file under its own name, and the
  short name now lives in a **twin file beside it** — `commands/rlt.md` mirrors `commands/test.md`
  body-for-body. `/relay:test`, `/relay:rlt` and the bare `/rlt` all reach the same instructions, and
  the first two both appear in the menu. Verified live against an installed build for all three.
- **Twins are generated, never hand-written** — `./scripts/gen-short-names.sh` writes them from the
  source command; `--check` fails on drift and runs in both the pre-push hook and CI, next to the
  version-sync check. Edit the source file; the twin follows.
- **`/gc` and `/tidy` gave up the bare global name they were quietly holding.** Both carried a
  leftover `name:` that claimed `/gc` and `/tidy` across every installed plugin — the exact collision
  the `rl` prefix exists to avoid. `/relay:gc` and `/relay:tidy` are unchanged.

Two cheaper mechanisms were tested against a live build first and neither works: a **symlink** beside
the source is ignored by the loader (`Unknown command`), and a **stub that injects the real body**
registers but then produces nothing — the same class of failure as the forwarding stub 1.10.0
dropped. That supersedes 1.10.0's "one command, one file" note for authors: two names need two files,
and the second one is generated.

## 1.10.0 — every command tells you what it takes

Relay had 22 commands and no way to ask any of them a question. The arguments existed — `plan-only`,
`audit`, `dry-run`, `no-verify` — but they lived in an `argument-hint` you see for a moment while
typing, or in a doc you'd have to leave the terminal for. The words that work on *every* command
(`small`/`large`, `terse`, `plain`, `solo`) appeared in three hints out of 22. And the whole set was
namespaced `/relay:`, so the shortest command in the loop was 11 keystrokes before its arguments.

**Added**
- **`?` on any command prints its usage and stops.** `/relay:test ?` (or `help`, `--help`, `-h`)
  lists every argument that command takes, one row each, plus the per-call words and the config keys
  it reads — then does nothing else. No PR opened, no tools run. `/relay:help test` prints the same
  block, and `/relay:help` alone still prints the whole map.
- **A `## Usage` block in all 20 argument-taking commands**, directly under the frontmatter — the
  single source both surfaces read, and now part of the command shape in
  [authoring-skills](docs/authoring-skills.md).
- **Short names for the ten loop commands.** `/rlt` runs `/relay:test`, `/rln` `/relay:next`, `/rls`
  `/relay:ship` — bare, no prefix, from anywhere; `/relay:rlt` and the full `/relay:test` land on the
  same file. Same arguments, `?` included. The `rl` prefix on the bare form is deliberate: a bare
  name is global across every installed plugin and Claude Code silently drops one that collides, so
  `/rlt` is safe where `/t` would be a coin toss. Full names are unchanged — nothing you type today
  stops working.
  The short name is a `name:` line on the command itself, **not** a second command that forwards to
  it: the forwarding version was built first and dropped, because reaching the target meant executing
  a hop, and that hop failed in four of five test runs. Verified live against an installed build —
  `/rlh`, `/relay:rlh` and `/relay:handover` all print handover's usage.
- **`/fix` finally has an `argument-hint`** — the one command that never showed one.

**Changed**
- **`/deploy` moved out of the loop and into support.** It was sitting in the main line of `/help`,
  the README and the quickstart as though every lap ran it, when it only applies to projects whose CI
  builds PR previews — `/test preview` is what reaches for it. The spiral now reads
  `explore → refine → next/continue → test → review/fix → ship → persist`. The command itself is
  unchanged and still there.

## 1.9.1 — the other half of the loop

1.5.0 taught `/next` to carry the autonomy policy into the build, and 1.8.0 gave it a moment to ask
about one. Both landed in `/next` only — but `/next` starts work that has no handover yet, and every
*resumed* thread comes back through `/continue`. So on any thread past its first lap, `/relay:continue
<handover> solo` parsed the handover path, silently dropped the `solo`, and stopped at every decision
anyway. Worse than an error: it looked like it worked. (`verbosity` and `audience` words *were*
honoured there, which is what made the gap easy to miss.)

**Fixed**
- **`/continue` resolves and carries `autonomy.decide`** — the same Step 0 resolution as `/next`
  (local prefs → project default → `ask`), the same per-call `ask`/`challenge`/`solo` word, and the
  same carry-into-the-build clause at Step 4. Two tabs can now resume two threads at two levels.
- **The first-decision gate runs in `/continue` too**, with an explicit hand-off: whichever command
  fires it first, the other stays silent — **one gate per repo, not one per command**.
- **`ask|challenge|solo` is in both argument hints**, so the picker shows the words instead of leaving
  them to be learnt from the docs — the same discoverability miss 1.8.0 fixed for `/config`.

## 1.9.0 — one fact, one home

Promoting a lesson to a guardrail, a guide or an ADR left its AI-memory copy sitting there. Nothing in
the lifecycle ever removed it, so the rule now existed twice, in two places free to drift — and the
next session could read either one.

Found by auditing a real repo after a week of use: **151 memories, 636 KB**, of which five were rules
already written word for word into the project's own guardrail files. A sixth appeared the day after
the audit — a filter-privacy rule whose memory said, correctly, that it belonged in the design guide
beside where filters are declared. It was written there. The memory stayed anyway.

**Added**
- **`/persist` retires what it supersedes.** Step 4 now looks both ways: as well as deduping the new
  write against its target, it checks whether AI memory already holds that fact from an earlier lap,
  and classifies each hit **retire** (fully carried by the durable write), **trim** (keep only the part
  with no repo home) or leave alone.
- **A Retiring block at the Step 5 gate**, under the harvest table, so a removal is approved in the
  same breath as the write that causes it — never silently. The user can keep any memory proposed for
  retirement.
- **Ordered removal in Step 6**, last and only for writes that actually landed: a memory goes only
  after the durable write replacing it is committed, so a failed or rejected write never costs you the
  copy you had.

**Changed**
- **One fact, one home** is now stated in the routing table: a lesson written to a guardrail, the
  design system, an ADR, a procedure or a how-to is **not also** written to memory. Memory is for the
  fact with no repo home — a machine reality, a working agreement, a gotcha belonging to no document.
- `/persist` is the only command that removes an AI memory, and only the one this lap superseded.
  General tidying of the memory layer stays out of scope.

## 1.8.0 — a question with no moment never gets asked

The sibling of 1.7.0's lesson. `autonomy` was kept out of `/config`'s guided pass on purpose — how
much a session decides alone is a trust decision, and answering it while picking a verbosity is how
you get an answer nobody meant. But "not in the guided pass" was implemented as *nowhere*: it wasn't
in `/config`'s argument hint either, so the picker never revealed it, and the only route in was typing
a word you had no way to learn. The default is the most conservative option, so nothing broke — it
just meant every driver stopped at every design decision forever, unaware there was a dial.

**A policy question needs a moment, and setup is usually the wrong one.** The right moment is when
the thing it governs is on screen.

**Added**
- **A one-time autonomy gate in `/next` (Step 5.4).** At the *first* decision that outlives the lap,
  the session puts the decision to the driver as always — and only once it's answered, offers the
  policy with that decision still on screen as the example: keep asking, hand calls like it to the
  **challenger** agent, or decide alone. The answer is written to `relay.config.local.json` (per-driver,
  gitignored), **including an explicit `ask`**, which is what stops the gate ever firing again. Set
  `autonomy.decide` up front, or pass a per-call `ask`/`challenge`/`solo` word, and it never fires at
  all. It never replaces the decision, and never fires on an `autonomy.escalate` category.

**Fixed**
- **`autonomy` is in `/config`'s argument hint**, so the picker shows it alongside the other areas.
- **Doc drift in `docs/conventions.md`:** the "full schema" reference had no `autonomy` block at all
  (nor the split across the two config surfaces), and its `hooks` example omitted `release` — both
  shipped in 1.5.0/1.6.0 and documented everywhere except the schema everyone reads first. The
  per-call override list and the Step 0 resolution snippet now carry `ask`/`challenge`/`solo` too.
- **`review.agents` no longer claims `/config` writes it** — only `/adopt` does — and it finally has a
  changelog entry, backfilled under 1.2.0 where it actually shipped.

## 1.7.0 — a policy with no trigger never fires

`tidy.level` defaults to `standard`, which is documented as *"prune + trim"*. Prune has run on every
lap for months, because it is wired into `/handover` Step 4.5. Trim had the same policy, switched on
by the same default, and no trigger at all — so it never ran once. (Found on a real repo after a week
of use: **13 of the 50 rows in *Open threads* were ✅ done**, and the board `/next` reads before every
decision had grown to 127 KB. Its owner had never run `/tidy`, and had no reason to: the half of it
with a visible symptom was already automatic, and the half without one was silently inert.)

The general shape, worth stating: **a layer that accretes needs a trigger, and the level dial should
say what the trigger may do — not whether the work happens at all.**

**Added**
- **Per-lap TRIM** in `/handover` Step 4.5 (so also in `/ship`) — done rows leave *Open threads* and
  collapse to a one-line `✅ Done: <slug>` on their track, in the same worktree-safe commit that
  archives superseded handovers and reviews. `/tidy` Step 4 stays the canonical rule; every KEEP-live
  guard applies unchanged, and a near-done tail still keeps its row.
- **A one-time gate.** The first trim in a repo reports the count and the board's size and asks
  *"trim them from now on?"*, then records the answer as `tidy.ops.trim` and never asks again. Set
  `tidy.ops.trim` up front and you are never asked at all.
- **`lean` gained a voice** — it prunes as before, then *reports* what trim would clear without
  touching it. That is the rung for an owner who wants the signal and keeps the decision; `standard`
  is the rung for an owner who wants it handled.

**Changed**
- `/tidy`'s own docs now say plainly that you are not expected to remember to run it: hand-running is
  for the ops handover doesn't carry (MERGE, brief archival), for a repo that ships rarely, or for a
  deliberate sweep.

## 1.6.0 — one release per lap

`/ship` merged your work and stopped, leaving the project's version describing a past that no longer
exists. Cutting a release was a step that only happened when someone remembered it — and in a repo
with a release bot, that means a proposal PR sits open indefinitely. (Found on a real one: open three
weeks, 1,637 commits and 324 features landed behind it, version still reading the July number.)

**Added**
- **`hooks.release`** — the project's own way to cut a release, dispatched by **`/ship` Phase 5.6**,
  right after a successful merge. Merging a release bot's proposal, running a bump script, tagging:
  all of it stays the project's business. Relay only decides *when*, and the answer is **once per lap**,
  so a version number means "a session's work" rather than "sometime last month".
- **No hook ⇒ skipped silently.** Relay will not invent a release — no guessed version scheme, no tags,
  no edits to version files in a repo that never asked. If it spots an obvious mechanism (a release-bot
  PR, a release workflow, a `release` script) it says so **once** and offers to wire the hook. Non-fatal
  either way; a failed release never blocks the handover.
- `/config`'s hooks offer now includes `release` when the repo shows evidence for one.

## 1.5.1 — autonomy is per-session, not per-project

**Fixed**
- **`autonomy.decide` and `autonomy.budget` are per-driver, per-session** — read from
  `relay.config.local.json` (gitignored) with a **per-call `ask`/`challenge`/`solo` word in
  `$ARGUMENTS` winning**, exactly like `session`. 1.5.0 put them only in the committed project file,
  which forced every parallel tab to the same level — wrong, since "how much this tab decides alone"
  is a property of what the tab is doing. You can now run `/next solo` on plumbing in one window and
  `/next ask` on something you want a say in beside it.
- `escalate` and `log` stay **project-wide** in `relay.config.json`: what counts as a product decision,
  and where calls are recorded, are facts about the project, not the driver. A committed
  `decide`/`budget` still reads as the project default; local and per-call override it.

## 1.5.0 — decisions made without you, on purpose

Relay's agents all reviewed code that already existed, so the decision made *at minute forty of a
build* — the one that's expensive precisely because nothing is written yet — had only two outcomes:
stop and ask, or decide alone and hope. This adds a third, and a policy for when to use it.

**Added**
- **`challenger` agent** — challenges a technical decision **before** it's built. Takes two or three
  named options, what the caller already checked, what breaks either way, and the caller's own
  recommendation; grounds itself in the project's rules, prior decisions and real call sites; attacks
  the recommendation (what it forecloses, what becomes irreversible, who else changes when it's wrong,
  whether the framing itself is wrong); returns a ruling with the one observation that would reverse
  it. Deliberately **not** findings-shaped and **not** in the `/review` fan-out. **Refuses an
  underspecified brief** (`INSUFFICIENT BRIEF`) rather than doing the caller's thinking, and
  **escalates** anything that isn't an engineering call.
- **`autonomy` config block** (`/config autonomy`, jump-only — a trust decision shouldn't be answered
  in passing). `decide` (`ask`/`challenge`/`solo`, default `ask` = today's behaviour) governs what a
  session does at a decision that outlives the lap; `escalate` lists the categories that come back to
  the user at every level (default: user-visible, commercial, copy, consequential); `budget` caps
  challenges per lap (default 4 — needing more means the slice is too big); `log` records every call
  made without the user (default `<root>/decisions.md`). **Judgment gates only — safety gates never
  relax.**
- **`/next` carries the policy into the build** (Step 0 resolves it, Step 5 acts on it), so autonomy
  reaches the part of the lap that isn't inside a command.

**Changed**
- **`/ship`'s merge gate checks the green is against the CURRENT base** (`HEAD..origin/<base>` must be
  empty). A sibling session merging first invalidates a green run, and the old gate couldn't see it.
  This is what makes parallel sessions safe to merge without coordinating — whoever arrives second
  re-verifies rather than merging an untested combination.

## 1.4.0 — cross-check at both decision points, with a lens

Prior-art cross-checking now happens at the two points where it's cheapest, aimed differently at each:
**explore checks the *idea, after* shaping; refine checks the *build, as input* to grounding.**

**Added**
- **`/cross-check` takes a `conceptual` | `technical` lens** (a per-call word, or passed by the calling
  command). `conceptual` weights how others *frame and solve the problem*; `technical` weights how they
  *implement it* (algorithms, libraries, protocols, standards, failure modes); absent ⇒ both. Biases
  emphasis, not which sections of the reference frame exist.
- **`/refine` folds a technical cross-check into grounding (Step 2).** When a change introduces a novel
  or external-facing technical approach, refine now offers — once, content-gated — to run a `technical`
  cross-check *as a grounding source alongside the code scouts*, so the slices are shaped **with** prior
  art rather than corrected after. It's explore-aware: if the concept was already cross-checked, this
  one aims at the implementation delta. Scales to session size; skipped on routine changes.

**Changed**
- **`/explore`'s prior-art cross-check is now offered consistently** (Step 3.5), at the `conceptual`
  lens. The offer is a visible line at convergence; it auto-skips only genuinely trivial changes, and
  says so when it does — fixing the "sometimes offered, sometimes not" behaviour.

## 1.3.0 — verify is a step in the loop

The loop was **build → ship**, with `/test` sitting to one side as an optional "kick the tyres". That
put the review fan-out — the most expensive phase Relay runs — on changes nobody had exercised. Verify
is now a named step on the main line: **build → test → ship**.

**Added**
- **`hooks.env` (`{ up, down }`) — the project owns the local test environment.** `/test`'s local
  target brings an environment up *only* by dispatching the project's own command, and `/ship` calls
  `down` **only for an environment this session started** — never one it found already running. A local
  stack is routinely shared with a sibling session, and the project's own `down` command is the right
  place to be sibling-safe (to refuse, or no-op, when something else is still using it). Relay names
  the phase and sequences it; it never starts or kills a stack by hand.
- **`hooks.deploy` is now actually dispatched.** It was in the config schema and consumed by nothing.
  `/deploy` now treats a declared hook as the project's answer for how a PR preview is triggered, ahead
  of re-deriving one from CI config.
- **`test.target` (`preview` | `local` | `ask`)** — which environment `/test` verifies against.
  Absent ⇒ auto: preview if the project has one, else local. A per-call `preview`/`local` word wins.
- **No hook? Relay offers to write one.** `/test` (local) and `/deploy` (preview) each offer **once** to
  draft the project's command via the `authoring-skills` skill and wire it into `hooks`. Decline and
  they fall back to printing the run command from `CLAUDE.md` as a manual precondition — never to
  starting things themselves. This is the help Relay gives on an environment it deliberately doesn't own.

**Changed**
- **`/ship` gained a verify gate (Phase 2.5)** — between "ensure a PR" and the review fan-out. It looks
  for evidence the change has been exercised (a ticked `## 🧪 Test drive` section, or a `/test` results
  comment on the PR). Found ⇒ one line and carry on. Not found ⇒ **asks once**: run `/test` first, or
  review anyway. The answer holds for the rest of the run, and the gate stays silent on docs-only diffs.
- **`/next` and `/continue` now point at `/test` when a slice is built**, not at `/ship`.
- **`/test` picks its target explicitly** (Step 3, rewritten) instead of falling back to "local run" as
  an afterthought, and reports which target it used and whether it brought the environment up.
- **Docs re-shaped around the four-command path** — `/explore → /refine → /next → /test → /ship`.
  README's loop picture, the quickstart's numbered walk, and "a day in the loop" all carry the verify
  step now; `/help` moves `/deploy` into the loop table alongside `/test`.

**Fixed**
- **A live drift in `conventions.md`:** it claimed `/test` brings the fixture stack up via `hooks.test`,
  but `/test` never mentioned hooks at all. The hooks section now carries a table of every hook, who
  dispatches it, and what it's for.

## 1.2.2 — `/refine` executive summary actually compresses

**Changed**
- **`/refine`'s `informed`/`plain` STOP-gate is now a real executive summary.** 1.2.1 added audience as
  an *addendum* under Step 6's "show grounding / threat / slices" bullets, so it didn't bite — the full
  tables still rendered. Step 6 is now *structured by* audience: `informed` renders the decision(s) +
  recommendation, the **top 2–4 load-bearing reshapes** (not every finding, no `file:line` table), a
  one-line threat verdict, and slice **titles + count** — ~10 lines instead of ~50. `plain` is tighter
  still; `expert`/unset keep the full plan. Step 7 still writes the complete brief, so no grounding is lost.

## 1.2.1 — audience governs terminal altitude

**Changed**
- **`audience` now shapes how much depth surfaces in the terminal, not just prose register.** At
  `informed`/`plain`, Relay leads with the decisions and what changed and defers exhaustive evidence
  (`file:line` grounding tables, full acceptance detail) to the **written artifact**, which always
  keeps full depth — no grounding is lost, it just stops being dumped in chat. `expert`/unset keep
  today's full-detail terminal output. Applied first to `/refine`'s STOP-gate (its Step 7 already
  writes the complete brief), and generalised via the shared Output convention to the other
  report-heavy commands. Still additive: absent ⇒ no shaping.

## 1.2.0 — audience register

**Added**
- **New `audience` driver preference** — tunes the *technical register* of Relay's prose, orthogonal to
  `verbosity` (which tunes *how much* it says). Three levels: `plain` (non-technical, no jargon),
  `informed` (architecture, trade-offs and named patterns; no code/syntax/flags unless they're the
  point or you ask), `expert` (full implementation depth). Lives in the gitignored
  `relay.config.local.json` like `verbosity`/`session`, accepts the same per-call override words
  (`/refine informed`), and shapes narrative prose only — never a required code snippet, a STOP-gate,
  or the substance of a table or the final landing. **Absent ⇒ no shaping (today's behaviour)** —
  additive and fully back-compatible.
- **Project-declared review agents** (`review.agents`) — a project can register its own
  `.claude/agents/*.md` and `/review` folds it into the same machinery as the built-in ten: `gate`
  (a built-in signal name or a `{ "paths": [glob…] }` match) decides whether it runs for this diff,
  `tier` (`safety` uncapped / `cappable`) whether the session cap applies, `scope` + `priority` where
  it sits in the fan-out — then one merged report. Written by `/adopt`'s keep-and-hook triage
  (register-as-review-agent) or by hand; absent ⇒ just the built-in specialists. Shipped in this
  release but missing from these notes until 1.7.x — recorded here for the record.

## 1.1.0 — knowledge persistence + housekeeping

Generalises two disciplines proven by hand on a multi-year ERP into config-driven, size-tunable
capabilities. Additive and back-compatible: unset config keeps today's behaviour, and existing repos
are unaffected until they accept an offered migration.

**Added**
- **`/persist` is now a config-driven distiller.** A `persist.level` preset — `none` (codebase only) ·
  `lean` (memory + release notes) · `standard` (today's harvest) · `full` (+ **ADRs**, procedures,
  how-tos) — tunes how much a lap harvests, with a per-kind `persist.kinds` override. ADRs use a
  parallel-worktree-native **date-slug, no-counter** convention (`YYYY-MM-DD-<slug>.md`, supersede
  never delete).
- **Durable knowledge lives OUTSIDE `<root>/` by default** — ADRs → `docs/decisions`, procedures →
  `docs/procedures`, how-tos → `docs/how-tos`, guardrails → `docs/guardrails`, all overridable via new
  `paths.*` pointers — so durable output outlives Relay. `/init` **offers** to externalise a legacy
  `<root>/knowledge/` (never forced); `/exit` now preserves external durable docs instead of discarding
  them.
- **New `/relay:tidy`** — recurring, idempotent housekeeping for the **volatile** layer: prune spent
  handovers/reviews, trim done rows off the board, merge same-unit briefs. Parallel-worktree-safe
  (temp-index commit with a retry-replay loop), with a hard broken-link gate and a **Distilled-marker**
  invariant so it never prunes un-distilled knowledge. `tidy.level` / `tidy.ops` / `tidy.retention`
  tune it; `/handover`'s per-ship archival is its per-lap subset.
- **`/persist` stamps a `**Distilled:**` marker** on each harvested brief — the contract `/tidy` reads
  before pruning.
- **`/config` gains `persist` and `tidy` jump-areas**, and `paths` covers the new durable destinations.

**Changed**
- `persist` config is now a nested block (`persist.cadence` + `persist.level` + `persist.kinds`); the
  flat `persist: "ask"|"always"|"never"` is still read as `persist.cadence` (back-compat).

## 1.0.9 — brownfield guardrails sweep

**Added**
- **`/config` offers a guardrails *sweep* on a brownfield repo.** When it detects an established
  project, Layer 2 scans for real standards material and **names what it found** — a design guide /
  design-system package (`ui`), an OpenAPI/GraphQL schema or spectral ruleset (`api`), ESLint/Prettier/
  tsconfig (code style), a `SECURITY.md`/auth layer (`security`), a test runner (`testing`) — and offers
  to "sweep this repo for guardrails" from what's actually there, handing off to `/guardrails`.
- **`/guardrails` discovery is now an explicit repo sweep** — it inventories existing config/standards
  *files* (lint/format/tsconfig, OpenAPI/spectral, `SECURITY.md`, design guide, test config), not just
  which dimensions exist, and cites the artifact seeding each dimension's baseline/`extends`. Grounded
  in real files, evidence-cited — never a guess about the user (per the 1.0.8 principle).

## 1.0.8 — no fabricated familiarity

**Fixed**
- **`/relay:config` no longer characterises the user back at themselves.** On a fresh session it was
  synthesising a working "style" from the global `CLAUDE.md` and presenting option descriptions as
  "Fits *your* … style" — presumptuous, and wrong to assert about someone it doesn't know. Option
  descriptions are now **neutral** (what each does), and any suggested default must rest on a concrete,
  current signal and be phrased tentatively. Stated as a cross-cutting principle ("No fabricated
  familiarity") in `conventions.md`, so it binds every command, not just `/config`.

## 1.0.7 — namespace note on the remaining docs

**Changed**
- Added the `/relay:`-namespace one-liner to `docs/the-board-model.md` and `docs/conventions.md` (they name commands in prose but lacked it), so the whole doc set is consistent.

## 1.0.6 — copy-able docs + new-user nudges

**Changed**
- **Runnable command examples now carry the `/relay:` prefix** across README, quickstart, and
  day-in-the-loop — so they're exact copy-paste (a bare `/init` isn't a command and tab-completes to a
  built-in). Prose keeps the bare names for readability, and each doc now says so up front.
- **New-user nudges.** Since Claude Code controls the `/relay` autocomplete order (it can surface `/gc`
  or `/fix` first — not plugin-influenceable), the README and quickstart now point a new user's first
  keystroke at **`/relay:help`** (the one-screen map) rather than the picker.
- **`/refine` is now a real beat in the day-in-the-loop walk** (shape → **ground** → build), not a
  skippable sidebar, and it's in the flow diagram.

## 1.0.5 — docs refresh + `/help` links

**Changed**
- **`/relay:help` links to the GitHub repo docs** (quickstart, board model, day-in-the-loop,
  conventions, CHANGELOG) instead of local file paths — so "more info" is one click away.
- **Full docs pass to 1.0.4.** Swept the last `budget/tier`→`session` leftovers (README, board-model,
  day-in-the-loop); added `/help` to the README command tables and `/config` · `/help` · `/exit` to the
  quickstart daily rhythm; and re-based `docs/ssdlc-roadmap.md` from "1.0 in progress" to "1.0 shipped,
  now on 1.0.x" (its arc is fully delivered — the CHANGELOG is the authoritative record; Reach R1–R3 is
  the live next). Config's `tier` note marked superseded by `session`.

## 1.0.4 — layered config

**Changed**
- **`/relay:config` is now layered gentlest-first**, instead of opening with a flat "here's all six
  areas, pick" table (which was the questionnaire the command was meant to avoid). It now: **leads with
  the two cheap driver prefs** (session + verbosity, one brief question each) and STOPs — most users are
  done there; then, only on a yes, gives a **compact, evidence-based offer** for the project knobs
  (guardrails → `/guardrails`, hooks → `/adopt`), offered only when the repo shows evidence for them;
  and keeps the **structural knobs (`root`, `paths`) out of the guided flow entirely** — reachable on
  demand via `/relay:config paths` / `root` for someone who's read the docs. The full current-vs-default
  table is now a reference (`/relay:config show`), not the opening menu.

## 1.0.3 — the config front door

**Added**
- **`/relay:config` — guided config, opt-in depth never a gate.** The config principle stated plainly
  and given a home: you can go from zero to shipping without ever opening a config file (absent keys are
  defaults), and this command is the *"now I want more"* surface. It **shows what's set vs available**
  (the discoverability an empty default file can't give), **proposes only what's worth setting for this
  repo** (not a blank questionnaire), and **walks the agreed ones as Q&A** — delegating the deep parts
  (`guardrails` → `/guardrails`, `hooks` → `/adopt`). Declining anything is a first-class answer.
  `/init` now offers it in one line rather than interrogating; `/help` and the README list it. The
  "opt-in depth, never a gate" rule is now the stated spine of the config system in `conventions.md`.

## 1.0.2 — the graceful exit

**Added**
- **`/relay:exit` — leave cleanly, the round-trip for `/adopt`.** Removes Relay from a repo without
  trapping anything: it **restores each adopted brief to where it came from** (the 1.0.1 provenance line
  records the origin), **exports** your Relay-created briefs (default `ideas/`), **discards** Relay's own
  bookkeeping (board, handovers, reviews, audits — all in git history), and **removes** config +
  the `.gitignore` line — leaving your **code and deliverable docs untouched**. Previews the full plan
  and STOPs before touching a file (`--dry-run` to preview only); lands as one `git revert`-able commit;
  refuses to proceed on uncommitted/in-flight work. So adoption is fully reversible — no lock-in.
- **Complete config reference in `docs/conventions.md`.** Because `/init` scaffolds no placeholder
  config (absent = default, each key added by the command that owns it), the full `relay.config.json` /
  `relay.config.local.json` schema is now documented in one annotated block, with the default for every
  absent key.

## 1.0.1 — the interaction layer

Additive polish from dogfooding 1.0 on a real repo — how Relay *talks to you* and *handles your
files*. New shared contracts live in [docs/conventions.md](docs/conventions.md).

**Added**
- **Session size replaces the budget tier.** The signal that sizes work isn't "which Claude plan" —
  it's **context appetite**: slice so a build finishes within the healthy part of a context window
  (~first half). `tier (free/pro/max)` → **`session (small/medium/large)`**, and it moves out of shared
  `relay.config.json` into a **gitignored `relay.config.local.json`** (a driver preference, switch-often,
  never inherited by teammates), with **per-call overrides** on every consumer (`/refine large`,
  `/next small`). A committed `tier` is still read as a back-compat fallback. `/refine` uses it to size
  slices; `/review`/`/next` fan-out follows.
- **Verbosity control.** `verbosity` = `terse | normal | verbose` in the same local prefs file, or a
  per-call word (`/next terse`). `terse` = banner + STOP gates + the landing, no narration.
- **`/relay:help`** — an on-demand capability map (lifecycle + every command, one line each), so the
  command set is discoverable and re-findable.
- **`/adopt` reconciles the existing `.claude/` setup.** Beyond docs, it triages a repo's existing
  commands/skills — **keep** (not covered) / **offer-remove** (redundant with Relay) / **keep-and-hook**
  — and writes an explicit **`hooks`** map so Relay phases dispatch the project's own automation
  (`{ "hooks": { "test": "test-stack" } }` → `/ship`/`/test` bring the fixture stack up via it).
- **Safety net for destructive ops.** Adoption/compaction/migration never leave a move unrecoverable:
  in git, git *is* the backup (commit-first, report the undo path); with no git, the original is copied
  to `<root>/archive/pre-adopt/` first. Every move is stated explicitly, and adopted briefs carry an
  `_Adopted from … (moved)_` **provenance line** so "adopted vs created" is answerable at a glance.

**Changed**
- **Consistent tabular output** — lists (shortlists, findings, plans) always render as GFM tables,
  never stacked `Field: value` records or ASCII separators (the `/next` shortlist regression), with
  terse cells + footnotes.
- **`/init` records nothing switch-often** — session/verbosity are no longer asked or written at init;
  it just gitignores the local prefs file.

## 1.0.0

The breaking cut, tagged **once**. Assembled on branch `1.0`; main stays on 0.14.0 until the
`1.0`→`main` merge. The whole additive 0.x arc (guardrails · budget/tier · `/refine` · `/persist` ·
`/deploy` · brownfield adopt) now sits under one stable major, with the lifecycle finally reading as
its verbs. Every additive 0.x feature carries forward unchanged.

**Changed (breaking)**
- **Command renames** — the lifecycle reads as its verbs; the `relay:` namespace already says "relay",
  so redundant prefixes/plumbing names are gone: `relay-init`→`init`, `whats-next`→`next`,
  `review-pr`→`review`, `fix-pr-review`→`fix`, `test-drive`→`test`, `wrapup`→`ship`,
  `garbage-collect`→`gc`. Unchanged: `explore`, `refine`, `continue`, `deploy`, `persist`,
  `guardrails`, `handover`, `cross-check`, `watch`, `version`.
- **Durable-state dir renames** — `pr-reviews/`→`reviews/` and `board-audit/`→`audits/` (the `pr-`/
  `board-` prefixes were historical). Every reference across commands, agents, and docs swept to match.
- **`/explore` is now purely context-free (explore→refine split)** — it shapes the idea *in the
  abstract* and never inspects the project; the pre-build **fit check** and all code-grounding moved to
  `/refine`. Three clean stages: `/explore` shapes → `/refine` grounds → `/next`/`/continue` builds.

**Added**
- **Progressive setup — `/init` is now minimal, and adoption is gradual.** Onboarding was too heavy:
  init front-loaded a budget-tier question, a full dir tree, seeded stubs, and (in 0.14.0) a
  destructive import of your idea docs. Now `/init` does the *minimum* — a board and the two dirs the
  first commands write — and **nothing destructive**. On a brownfield repo it surfaces your existing
  idea/plan docs on the board **by reference** (left in place); on greenfield, an empty board → `/explore`.
  Everything heavier is **deferred and offered by the phase that needs it**: the budget tier is asked
  the first time a command fans out (`/review`/`/refine`/`/next`), guardrails is offered when `/refine`
  or `/review` finds none, and pulling legacy docs *into* Relay happens on touch or on demand (below).
- **`/adopt [area]` — gradual brownfield migration, with cleanup.** A dedicated, area-scoped command
  that brings existing material under Relay management: **work-inputs** (ideas/plans/todos) are **moved**
  into `briefs/` and **actualised** on the way in (cut what shipped, fix drift, tighten); **deliverable
  knowledge** (design guide, conventions) is **registered** as a guardrails `extends` overlay *in place*
  and **compacted** by its domain steward (e.g. `ui-ux-designer` trims an accreted design guide). Code
  is left untouched. Always previews a triage table and STOPs before touching a file; scope narrows the
  blast radius (`/adopt ui`, `/adopt ideas/finance*`, `/adopt --all`). `/refine` does the same pull-in
  **on touch** for a single idea, so a brownfield repo becomes pristine as you work; `/adopt` is the
  bulk fast-forward. (This is where 0.14.0's destructive import moved — from an init default to a
  deliberate, scoped, non-destructive-by-surprise command.)
- **Per-path config** — `root` generalises to a uniform `paths` resolver: relocate any single logical
  path independently (`{ "paths": { "knowledge": "docs" } }`), resolving `paths[name]` else
  `<root>/<name>`. List only what you move; no config ⇒ everything under `relay/` as before.
- **Epic modelling** — a slug convention (`track/epic/slice`) + a grouping view in `/next`; no board
  schema change. `/refine` slices a large item into an epic; `/next` recommends the next unstarted slice.
- **Reflect loop** — the spiral's return edge, formalised in `/test`, `/ship`, and `/persist`: after a
  result is seen, re-enter `/explore` (new idea) or `/refine` (same idea, changed) with what you learnt.
- **Security shift-left, end to end** — `/test` now turns a `/refine` threat model into scenarios that
  prove each mitigation holds; combined with the always-on security review and `/deploy`'s security
  gate, a modelled threat is verified, not assumed.
- **1.0 migration path** — `/init` detects a pre-1.0 layout (`pr-reviews/`/`board-audit/`) and offers
  to rename it (history-preserving where there's git), the only file-level migration a consumer repo
  needs.

**Migrating from 0.x:** commands are just what you type — use the new names. In each repo, run
`/relay:init` once; it offers the dir rename. The destructive brownfield-adopt introduced in 0.14.0
rides along in this major.

## 0.14.0

**Changed**
- **`/relay-init` now *adopts* a brownfield repo's existing work instead of just pointing at it.**
  0.12.8 surfaced pre-existing idea docs on the board by reference — which left two homes (a mostly
  empty `relay/briefs/` beside the real `ideas/`). Init now **triages** existing docs by intent and
  acts on each:
  - **Work-inputs** (ideas, specs, plans, TODOs — *volatile*, spent once shipped) are **imported into
    `<root>/briefs/`** and put on the board. This is Relay's job: track them to done, then archive.
  - **Deliverable knowledge** (design guide, DB conventions, architecture, tone-of-voice, runbooks —
    *durable*, still true after shipping) is **left with the code** to feed the knowledge layer
    (`/guardrails` reads it, `/persist` grows it).
  - **Code/content/assets** are left untouched.

  Init presents the triage table and **STOPs for approval before moving anything**. The import
  **preserves git history** (`git mv` for tracked files) and rewrites path references to moved files;
  name-based `[[wikilinks]]` survive. A doc that's both a plan and a decided model is imported as a
  brief now — `/persist` lifts its durable decision into the knowledge layer when the work ships.
- **`/relay-init` no longer assumes git.** Not every project is a git repo: the adoption move falls
  back to a plain `mv` when there's no git (or the file is untracked), and the final commit is skipped
  (init never force-`git init`s a project that isn't under version control) — the files are just
  written in place and the report says so.

## 0.13.0

**Added**
- **`/relay:version` — a CLI-style `--version`.** Prints the Relay banner + version, so you can
  confirm which plugin version is actually loaded in a session. Like the init banner, the version is
  hardcoded in the command file (no runtime read is possible — `${CLAUDE_PLUGIN_ROOT}` doesn't expand
  in command bash), which is the more useful behaviour anyway: it certifies the *loaded* command file,
  so a stale cached command shows an old version. (Maintainers bump the string in `plugin.json`,
  `/relay:version`, and the `/relay-init` banner together.)

**Tooling**
- **Version-sync guard** (`scripts/check-version.sh` + a `version-sync` GitHub Action). Because the
  version is mirrored across `plugin.json`, `marketplace.json`, and the two command banners, the guard
  fails the build on any drift — and also if the current version has no CHANGELOG entry. Runs in CI on
  push/PR; run it locally before a release.

## 0.12.8

**Fixed**
- **`/relay-init` (populated repo) now surfaces pre-existing idea/plan docs on the board.** It seeded
  tracks from the *code* but ignored docs where the user had already written down intended work — on
  a real brownfield repo (an `ideas/` folder of project baselines) that silently dropped every one of
  them from the board. Init now scans for intended-work docs (`ideas/`, `briefs/`, `rfcs/`,
  `docs/*-project.md`, `HANDOFF.md`, …), adds each as a 💡 icebox item whose `Detail` **points at the
  doc in place** (adopt, never move/rewrite), and reports how many it surfaced. Pure reference/
  convention docs (design guide, DB conventions) are correctly left off the board.

## 0.12.7

**Fixed**
- **Next-step suggestions now show the full `/relay:` prefix.** `/relay-init` and `/explore` handed
  users bare command names (`/explore`, `/whats-next`, `/refine`) that can't be invoked by copy-paste
  — a bare `/explore` isn't a command and tab-completes to the built-in `/export`. The actionable
  "next move" lines now show `/relay:<name>` and note to tab-complete after the colon.

## 0.12.6

**Fixed**
- **`/relay-init` banner is now unskippable.** It was phrased as a soft note and competed with the
  "run quietly / compact" output discipline, so the model could drop it — defeating its whole
  version-certification purpose. It's now a non-negotiable directive that explicitly overrides the
  quiet-mode discipline (which is scoped to "everything after the banner").

## 0.12.5

**Changed**
- **`/relay-init` banner gains a byline** — `by Line20 · @eriklenaerts` under the tagline.

## 0.12.4

**Changed**
- **`/relay-init` opens with an ASCII `Relay` wordmark banner** (tagline + version) instead of a plain
  version line — a proper CLI-app header. Same version-certification purpose as 0.12.3: the version is
  baked into the banner, so a stale cached command prints an old banner (or none at all).

## 0.12.3

**Added**
- **`/relay-init` prints the running version first** (`⏺ Relay v0.12.3 · /relay-init`). Because the
  version is hardcoded into the command file, it certifies *which command file actually executed* — so
  if it shows an older number than the installed plugin, the session is running a **cached** command
  and needs a reload. This directly surfaces the "am I running the version I think I am?" trap.
  (`${CLAUDE_PLUGIN_ROOT}` doesn't expand in a command's bash, so a runtime read isn't possible;
  hardcoding is both the only option and the more correct one here — a runtime lookup could read a
  different cached copy than the file that's running. Maintainers bump the one string per release.)

## 0.12.2

**Fixed**
- **`/relay-init` greenfield detection now counts untracked files too.** It read only *tracked*
  files, so a freshly-scaffolded-but-uncommitted project (untracked files only) wrongly looked
  greenfield. Now checks tracked + untracked (`git ls-files --others --exclude-standard`), so an
  uncommitted real project is correctly treated as populated.

## 0.12.1

**Fixed**
- **`/relay-init` no longer invents work from a folder name.** On a truly empty repo it was seeding
  speculative tracks, a roadmap narrative, and a placeholder brief guessed from the directory name
  (a `todo-app/` folder became a fabricated `foundation`/`tasks`/`ui` board) — content the user then
  had to delete, and which left them unsure what was real. Init now **detects greenfield vs
  populated**: a populated repo is inspected and seeded with real tracks as before; a **greenfield**
  repo gets the **structure only** — an empty board, a roadmap header stub, no brief — and the report
  points at **`/explore <idea>`** as the first move (not `/whats-next`, which would survey an empty
  board). The report is also **more compact** (output discipline: no per-step narration, no
  file-content recaps) and now prints the one-line lifecycle so the next move is obvious.

## 0.12.0

**Added**
- **`/deploy` — orchestrate and verify a PR preview, then hand it to `/test-drive`.** Fifth increment
  of the Secure-SDLC arc, and phase (h). It turns "a preview might be building somewhere" into "here
  is a verified, security-gated URL to click through" — and it's deliberately **thin: it never
  deploys anything itself.** It only drives the **project's own pipeline**: discover how the repo
  previews a PR (a documented URL pattern, a `gh pr checks` deploy check, a CI job), ensure the build
  ran (nudging only through the project's own trigger), wait for it (bounded, non-thrashing), then:
  - **health-check** the resolved preview URL actually responds — a green check can still front a
    broken app;
  - **security-gate** it — require the project's own security checks (SAST/dep/secret scan) green for
    the SHA and confirm the target is an ephemeral **preview** env, never prod. A failing security
    check stops the flow; no security checks configured is reported as a gap (a `/persist` candidate).

  No preview mechanism ⇒ it says so and stops (testing falls back to a local run) — it never invents
  infrastructure. That "use the pipeline, never replace it" boundary is what lets one command span
  Vercel previews, review-env containers, and beyond without special-casing a vendor. `/test-drive`
  now points at `/deploy` to gate a preview before driving it.

See [docs/ssdlc-roadmap.md](docs/ssdlc-roadmap.md) — this is increment #5 of the additive 0.x arc.

## 0.11.0

**Added**
- **`/persist` — harvest what a lap taught back into the living knowledge.** Fourth increment of the
  Secure-SDLC arc, and phase (j): the step that makes the spiral *compound* instead of leaking each
  session. After a lap (a merged PR / a slug), `/persist` reads the diff, its review report, the
  brief's threat model, and the handovers, and extracts only the **durable, non-obvious** lessons —
  applying memory's "was it non-obvious, and will it recur?" test so the knowledge layer stays sharp,
  not bloated. It routes each lesson to a surface:
  - **Guardrails** — a recurring review finding or security bar becomes a rule in the dimension's
    **`extends` overlay** (the project's house rules). It **never mutates a shipped baseline** —
    establishing a dimension stays `/guardrails`' job; `/persist` only grows the overlay, wiring a new
    house-rules file into the config's `extends` array surgically when one doesn't exist yet.
  - **Design system** — a new pattern/token/component joins the design-system doc, generalising the
    stewarding `ui-ux-designer` already does for one guide.
  - **AI memory** — a non-obvious decision + its why, one fact each.
  - **Release notes** — a human-readable, user-benefit summary of what the lap shipped, in the
    project's copy voice (British English), grouped by release. This is the *outward* deliverable and
    is **not** filtered by the non-obvious test: every user-visible change earns a note (gated on
    "would a user notice?"), while a purely internal lap gets none. Distinct from a dev CHANGELOG —
    it's the human companion, not a copy. Lives at `<root>/knowledge/release-notes.md`, relocatable
    via `paths["release-notes"]`.

  Architecture/ADR/ops/manual targets are **captured as deferred** (later persist slices), never
  silently dropped. `/persist` offers before it writes (the knowledge layer is shared, main-owned
  project truth) and **never writes code**. "Nothing to persist" is a valid, sprawl-respecting outcome.
- **`/wrapup` now offers `/persist`** after the merge, before handover (Phase 5.7) — a non-fatal
  offer, skipped for a routine change. (At 1.0 this becomes a first-class phase of `ship`.)

See [docs/ssdlc-roadmap.md](docs/ssdlc-roadmap.md) — this is increment #4 of the additive 0.x arc.

## 0.10.0

**Added**
- **`/refine` — groom a shaped idea against THIS project.** Third increment of the Secure-SDLC arc,
  and phase (c) of the spiral: the bridge between `/explore` (which shapes an idea *in the abstract*)
  and `/whats-next` (which builds it). `/refine` takes an existing brief and grounds it in the
  project — reading the actual **code** (what to reuse, what not to break), the **guardrails** from
  `/guardrails` (turning each active dimension's bar into an explicit slice requirement), and the
  project's **memory/knowledge** (so settled decisions aren't re-litigated). It then does two
  distinctive things:
  - **A threat model, content-gated** — whenever the change has a security/privacy surface, it walks
    assets → trust boundaries → threats → mitigations against the `security`/`privacy` guardrail bar,
    and folds each mitigation into a slice as a requirement. Security is designed in, not bolted on.
    A change with no threat surface says so and skips.
  - **Budget-aware slicing** — it re-cuts the slices to the `tier` from increment #2: `free` → small,
    sequential, one-at-a-time; `pro` → moderate, parallel where independent; `max` → may decompose
    into an epic of parallel threads. Each slice carries its acceptance criteria (guardrail
    requirements + threat mitigations).

  It **never writes code** and **never writes guardrails** (that's `/guardrails`/`/persist`) — it
  grooms the brief in place and STOPs for approval before writing. Fully back-compatible: no
  guardrails ⇒ it skips that layer; `unset` tier ⇒ it slices by natural seams.

See [docs/ssdlc-roadmap.md](docs/ssdlc-roadmap.md) — this is increment #3 of the additive 0.x arc.

## 0.9.0

**Added**
- **Budget tier — one signal that scales fan-out to the driver's Claude plan.** Second increment of
  the Secure-SDLC arc. `/relay-init` now asks once for a **`tier`** — `free` / `pro` / `max` — and
  writes it to `relay.config.json`. Two commands read it today:
  - **`/review-pr`** caps how many specialists fan out. A **safety core** — `security-specialist`
    (always), `test-engineer` (runs the suite), `dbms-specialist` (migration safety) — is *never*
    capped; the remaining content-selected specialists fill the budget by risk (`free` → +2, `pro` →
    +4, `max` → no cap). Anything the budget defers is logged in the report's *Skipped specialists*
    with a "re-run standalone for full coverage" note — never a silent drop.
  - **`/whats-next`** scales the verify/audit research fan-out (`free` → ~4 contenders, `pro` → ~8,
    `max` → ~10); an L3 audit stays exhaustive but warns and offers to scope on `free`.
- **Fully back-compatible.** Absent `tier` ⇒ **no cap anywhere** — every command behaves exactly as
  in 0.8.0. Budget shaping is opt-in: a repo that never sets a tier sees no difference. Later
  increments (`/refine`, `/test`) will read the same signal for slice size and test depth.

See [docs/ssdlc-roadmap.md](docs/ssdlc-roadmap.md) — this is increment #2 of the additive 0.x arc.

## 0.8.0

**Added**
- **`/guardrails` — establish what "good" means for a project, as layered guardrails.** First
  increment of the Secure-SDLC arc. Guardrails are **per-dimension** (`api`, `ui`, `security`,
  `privacy`, `testing`, …), **opt-in** (a dimension applies only if the project has it — a simple
  site runs fewer than a full ERP), and each resolves in three layers: **`extends` (the project's
  house rules — local file or URL, win on conflict) > a named `baseline` > Relay's default**. So the
  same command is opinionated (every active dimension ships a real default), adaptable
  (`api.baseline: zalando` swaps the ruleset), and extensible (overlay your own). `/guardrails` runs
  a discover-then-ask interview, writes a `guardrails` block to `relay.config.json` and prose docs
  under `<root>/knowledge/`, and STOPs for approval before writing.
- **Review specialists resolve guardrails.** `api-architect`, `ui-ux-designer`,
  `security-specialist`, and `privacy-specialist` now judge against the *resolved* guardrails for
  their dimension (`extends` > baseline > default) instead of ad-hoc defaulting — with a fully
  back-compatible fallback: no config / no dimension / no doc ⇒ their existing default behaviour,
  unchanged. A repo that never runs `/guardrails` sees no difference.

Shipped default API baseline is **`vendor-neutral-rest`**; Zalando / Microsoft / Google-AIP are
selectable adaptations (bundled rulesets land in a later slice — until then, point a baseline at a
ruleset path you supply). See [docs/ssdlc-roadmap.md](docs/ssdlc-roadmap.md) for the full arc.

## 0.7.0

**Added**
- **Configurable root — adopt Relay without moving a file.** Relay's durable state (board,
  roadmap, briefs, handover, archive, board-audit, pr-reviews, reference) used to be hardcoded
  under `relay/`; a repo that already keeps this state elsewhere couldn't use the commands at all.
  Now the root is **configurable per repo**: drop a `relay.config.json` at the repo root with
  `{ "root": "docs" }` and every command reads and writes `docs/board.md`, `docs/handover/…`, etc.
  Every command resolves the root once at the top (a "resolve the Relay root" step) and interpolates
  `<root>/…` throughout; `continue`/`whats-next` add a soft existence check that points at
  `/relay-init` if the configured root has no board. **Fully back-compatible** — no config ⇒ root is
  `relay/`, so existing repos are unchanged. `/relay-init` gained `--root <dir>`: it writes the
  config (when non-default), scaffolds under the chosen root, or — if a board already exists there —
  **adopts** the existing structure by writing only the config, wiring a bespoke predecessor to the
  `relay:*` commands with zero migration. Docs (quickstart, the-board-model) document the root and
  the override.

## 0.6.0

**Added**
- **`/test-drive`.** After a chunk of work, open (or reuse) a draft PR and write a
  **consistent, structured test plan** into it — preconditions, happy path, and the
  edge/error/tenant-isolation cases an LLM skips by default — always the same shape, so testing a
  Relay PR is muscle memory. Grounds every step in the real diff and the project's `CLAUDE.md`
  invariants. Where the project publishes a **preview deploy** per PR, the plan targets that URL;
  otherwise it falls back to local-run steps. It can then **drive the happy path in the browser**
  against the preview (`drive`, or it asks once), running the fail-closed non-happy checks, capturing
  a GIF, and posting pass/fail back to the PR — with guardrails (no destructive actions unless
  authorised, isolation probes stay read-only). `plan-only` prints the checklist without touching a
  PR. It never merges — that's still `/wrapup`.

**Changed**
- **Worktrees are now keyed to the topic, not the slice.** One stable git worktree per topic/brief;
  the slice-branch rotates inside it. This ends the per-slice worktree pile-up and keeps a topic in
  one editor tab across `wrapup → clear → continue`. `/whats-next` reuses + re-baselines an existing
  topic tree (`reset --hard origin/main`) when clean, else creates one; `/continue` forks on whether
  the handover's slice already merged — resume the in-flight branch as-is, or (shipped) re-baseline
  and cut the next slice-branch; `/handover` now **keeps** the topic tree on loop-close (removes only
  when the topic itself is done); `/garbage-collect` treats a clean, merged tree whose topic is still
  live as a keepable resting tree, not an orphan. Exact `EnterWorktree`/`ExitWorktree` calls are
  spelled out in each command.

## 0.5.0

**Added**
- **`/watch` + cross-worktree dependency awareness.** `/whats-next` and `/continue` now run a
  **dependency pre-flight** before building: they scan the other live sessions (worktrees on
  disk + the board's in-flight rows), and if your work depends on a sibling thread's change
  that isn't on `main` yet — **PR or not; local and uncommitted work counts** — they surface it
  and offer to hold. `/watch` then parks the thread (⏸ `blocked-on: …`), watches the dependency
  land in the background (a PR merge, a board item reaching ✅, or a branch merging), and
  **auto-resumes** the work once it's on `main`. Detection is conservative + file-overlap by
  default (flags the clear cases, doesn't cry wolf).

**Changed**
- **`/brainstorm` renamed to `/explore`**, and upgraded: it now asks **one question at a time**,
  **offers a visual** (diagram/mockup) when a question needs one, **splits** an idea that's
  really several independent briefs, and **self-reviews** the finished brief for placeholders,
  contradictions, ambiguity, and scope creep before handing off. (Update any alias on
  `/brainstorm`.)
- **Docs surface Relay's strong points better** — a new **Token economics** section (how cold
  handovers, the tiny board index, and scoped/gated review keep context cheap, and where it can
  still improve), sharper parallel-safety and design-before-code framing, and a **realigned**
  "idea in one picture" diagram.

## 0.4.0

**Added**
- **`/cross-check`** — build a durable **reference frame** (`relay/reference/<topic>.md`) of how
  other products, standards, and prior art handle a problem, and check your approach against it
  for alignment, divergence, blind spots, and reinvention. Reusable and cumulative; uses web
  search when the environment has it, otherwise the model's own knowledge (flagged as such).
  `/brainstorm` now offers it at the end (Step 3.5) before a design is committed. `relay-init`
  scaffolds `relay/reference/`.
- **`/garbage-collect`** — reclaim orphaned worktrees left by sessions that skipped the happy
  path (crashed, or `/clear`ed without a handover). Not needed in normal use — `/wrapup` cleans
  up after itself; this is the off-happy-path escape hatch. Auto-removes only provably-finished
  sibling worktrees, reports the risky ones, never force-removes another session's tree.

**Changed**
- **Uniform review reports.** `/review-pr` now writes to one fixed template every time — set
  frontmatter (incl. a `counts` block), a standard Verdict line, findings in one identical
  per-finding format (`**ID** · area · file:line — problem. **Fix:** … (specialist)`) ordered
  🔴→🟡→🟢, and always-present section headings (empty ones say `_None._`). No specialist gets
  its own format; the report reads the same regardless of which ones ran.
- **`/next` renamed to `/whats-next`** — clearer about the question it answers, and less
  collision-prone. (If you had a habit or alias on `/next`, update it.)

## 0.3.0

**Changed**
- **Command tiers made explicit.** The README now separates the commands you *drive* the loop
  with (`/relay-init`, `/brainstorm`, `/next`, `/continue`, `/wrapup`) from the ones the loop
  *composes* (`/review-pr`, `/fix-pr-review`, `/handover`) — the latter carry an in-file note
  that they're normally run by `/wrapup` and standalone only when you specifically need one.

**Removed**
- **`/start-new`** is gone. Its jobs were folded into `/handover` (which `/wrapup` runs): a new
  Step 4.5 archives superseded handovers + old PR reviews into `archive/`, and Step 6 now also
  prunes dead worktree entries. End-of-session housekeeping now happens automatically at the
  end of every `/wrapup` — there's no separate cleanup command to remember. The one behaviour
  change: a finished **sibling** worktree is now *reported* for you to remove, never
  force-removed, so the loop can't clobber another live session's tree.

## 0.2.0

**Added**
- **`/brainstorm`** — the front of the loop. Turns a rough idea into a shaped brief on the
  board: it interrogates the idea one theme at a time, weighs two or three real alternatives
  (keeping the product/UX lens separate from the architecture/data-model lens), recommends
  one, and writes `relay/briefs/<slug>.md` + a board row. It never builds — `/next` picks the
  item up when you're ready. The ship loop is now **`/brainstorm → /next → /wrapup`**
  (`/wrapup` runs the review, merge, and handover at the end); `/handover` + `/continue`
  remain the mid-thread pause/resume pair for when you stop without shipping.

## 0.1.0

Initial release.

- **Commands:** `/relay-init`, `/next`, `/continue`, `/review-pr`, `/fix-pr-review`,
  `/wrapup`, `/handover`, `/start-new`.
- **Review agents** (dispatched by `/review-pr`): backend, frontend, ui-ux, api-architect,
  dbms, test-engineer, security, privacy, i18n, solution-architect — all stack-agnostic.
- **Meta-skill:** `authoring-skills`, for adding your own commands and agents.
- **Docs:** quickstart, the board model, a day in the loop, authoring guide.
- All workflow state namespaced under a single `relay/` folder in the target repo.
