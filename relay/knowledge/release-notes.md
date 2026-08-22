# Relay release notes

_Human-readable notes on what changed, in plain language. The dev-facing detail lives in `CHANGELOG.md`; this is its companion._

## Unreleased

### Improved

- **`/fix` now checks its own work.** When `/fix` applies a review's fixes, it re-reviews just those changes before reporting success — and pulls in the matching specialist (security, database, or backend) when a fix touched something risky. A fix that quietly breaks something next to it is now caught before it ships, instead of surfacing in the next review round.
