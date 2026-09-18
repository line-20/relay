# Relay release notes

_Human-readable notes on what changed, in plain language. The dev-facing detail lives in `CHANGELOG.md`; this is its companion._

## 1.22.0

### New

- **Pick a task back up on another device.** When you hand off or ship a piece of work, Relay now saves its resume state to `main` automatically. So you can open a fresh clone on another machine — a second laptop, or your phone — run `/rlc <slug>`, and carry straight on from where the last session stopped, with no access to the original working copy. If the save can't reach the remote (you're offline), the handover still completes exactly as before; the cross-device part simply catches up on the next hand-off.

### Improved

- **A broken hand-off now fails on the spot, not two sessions later.** The note one session leaves the next used to be taken on trust; now Relay checks it is complete and well-formed both when it is written and when it is read to resume. If something is missing or malformed, you find out immediately — at the hand-off — with a clear message to regenerate it, instead of a fresh session quietly picking up half a plan and stumbling. In normal use you'll never see this; it only speaks up when a resume would otherwise have gone wrong.

## 1.16.0

### Improved

- **`/fix` now checks its own work.** When `/fix` applies a review's fixes, it re-reviews just those changes before reporting success — and pulls in the matching specialist (security, database, or backend) when a fix touched something risky. A fix that quietly breaks something next to it is now caught before it ships, instead of surfacing in the next review round.
- **`/persist` no longer stops to approve what you already steered.** It banks the whole harvest — memory notes, release notes, guardrail and design-guide additions — and hands back a one-line summary of what landed, instead of a wall of text and an approval prompt. The only time it pauses is when it would drop wording that isn't saved anywhere else. Lessons that used to get stranded at the approval step now just land.
