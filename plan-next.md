# Alfie — next work

Date: 2026-09-20. Status: active in-house WIP.

## Direction

Restore Hermes's native assistant flow and keep the design small. Conversation history, memory,
voice transcription, image analysis, normal reads, research, browsing and reminders should work
without a classifier, mode prefix, scope grant or preliminary confirmation.

The general task-permission experiment was removed. It was too restrictive, repeatedly intercepted
ordinary requests and media handling, and made the bot nearly useless. Git history preserves the
experiment if any narrow implementation detail is useful later.

Keep safeguards close to concrete dangerous effects:

- Google sends, modifications, creates and deletes require an immutable exact-action Telegram
  approval. Reads do not.
- The command sandbox receives no Google credentials or personal-data mounts.
- Public browser/research workers remain isolated from gateway credentials and private networks.
- Email-watch remains report-only; it does not make account or personal-record changes.
- Login, payment and authenticated checkout remain manual owner actions.

## Near-term work

- Confirm native Telegram voice and image handling through ordinary use.
- Improve useful personal-record lookup without adding another general permission framework.
- Keep deployment and documentation simple; add tests only for compact, high-value boundaries.
- Maintain exact-action reconciliation, browser patching, backups and firewall-first startup.
