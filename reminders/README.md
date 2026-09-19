# Safe reminders

UC6. The `reminder` gateway plugin restores ordinary owner reminders without exposing Hermes's
general cron administration tool. It runs in the existing gateway and adds no service, container
or dependency.

`reminder-write` permits create, pause, resume and remove. `reminder-read` permits list only.
Creation forces `deliver=origin`, no extra toolsets and a `chat: Reminder for the owner:` prompt.
The plugin never accepts scripts, monitors, skills, work directories, context chaining, alternate
destinations or arbitrary cron fields. List and mutations filter by authenticated owner/chat plus
the complete safe reminder shape; foreign and general cron jobs are invisible.

At fire time `alfie_permissions.safe_reminder_job` validates the owner identity, marker, bounded
text/name, origin delivery and absence of every privileged field before granting a fresh `chat`
task with no tools. The existing frozen policy remains authoritative for older reviewed jobs and
fixed scripts. Safe dynamic reminders do not modify that policy.

Tests: `python3 -m unittest discover -s reminders -p 'test_*.py'`. `deploy.sh` stages the read-only
plugin for a coordinated deployment; do not replace its live bind-mounted files while the gateway
is running.
