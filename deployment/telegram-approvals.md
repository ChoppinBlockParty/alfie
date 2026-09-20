# Google exact-action Telegram approval

Google reads execute directly. Every supported Google send, modification, creation or deletion
instead queues the exact operation, arguments and bounded target context for review in the owner's
configured Telegram approval topic.

Only an authenticated owner callback on the bound review message can consume the action. Approval
is single-use, expires after 30 minutes and is invalidated by gateway restart. Chat text, model
arguments and content from email, documents or websites cannot approve it. Gmail reply recipients
are resolved before review; target metadata is checked again before execution. Unknown outcomes
are retained for manual reconciliation and are never retried automatically.

This is a connector-level safeguard for concrete account effects. It does not classify
conversation, reads, media, memory, browsing or scheduling, and it does not isolate arbitrary code
running inside the credentialed gateway.
