# Deployment acceptance — 2026-09-20

Alfie runs as four containers with firewall-first startup, no Docker socket, no personal-data or
Google-credential mounts in the command sandbox, and an isolated public research/browser worker.
Google writes use exact-action owner Telegram approval; Google reads are direct. Email-watch is
report-only. Backup recovery and the principal container/network boundaries have previously been
exercised; detailed history remains in git.

The general task-permission system was tried and removed. It was too restrictive, hindered normal
conversation, voice and image handling, and made the bot nearly useless. Hermes's native assistant,
media, memory, tool-selection and scheduling flow is restored. Safety remains at concrete effect
boundaries rather than a conversational classifier.

This is a small in-house WIP. Actual Telegram use is the primary integration feedback; automated
tests are retained only where they compactly protect a high-value subsystem boundary.
