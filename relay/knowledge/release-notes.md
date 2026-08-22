# Relay release notes

_Human-readable notes on what changed, in plain language. The dev-facing detail lives in `CHANGELOG.md`; this is its companion._

## 1.16.0

### Improved

- **`/fix` now checks its own work.** When `/fix` applies a review's fixes, it re-reviews just those changes before reporting success — and pulls in the matching specialist (security, database, or backend) when a fix touched something risky. A fix that quietly breaks something next to it is now caught before it ships, instead of surfacing in the next review round.
- **`/persist` no longer stops to approve what you already steered.** It banks the whole harvest — memory notes, release notes, guardrail and design-guide additions — and hands back a one-line summary of what landed, instead of a wall of text and an approval prompt. The only time it pauses is when it would drop wording that isn't saved anywhere else. Lessons that used to get stranded at the approval step now just land.
