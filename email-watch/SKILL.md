---
name: email-watch
description: Processed-email log. Read Gmail only when asked.
version: 1.0.0
author: Alfie
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Email, Gmail, Inbox, Todo, Travel, Calendar]
    related_skills: [records, google-workspace]
---

# Email watch

**The inbox is already handled.** The `email-watch` cron job runs every 30 minutes. It reads
each new inbox email **once**, records to-dos, events, trips and bills in the records store,
creates calendar events for confirmed bookings, keeps the current timezone in `USER.md` up to
date from trips, and reports anything important in the Telegram email topic.

## Rules

- **Do not scan, triage, summarise or re-read the inbox on your own initiative.** Do not
  re-report an email the watch already reported.
- **Read Gmail only when Slava explicitly asks** to find or read something in his email
  ("find me in my emails…", "what did X send about…"). Then use `google-workspace` as normal —
  re-reading is allowed for an explicit request.
- For such a request, check the log first — it is cheaper and often enough:

```
python3 /opt/data/scripts/email_watch.py find <word>     # received, sender, subject, summary, Gmail link
```

## Where the extracted facts are

```
python3 /opt/data/skills/personal/records/records.py due --within-days 30      # open to-dos and bills
python3 /opt/data/skills/personal/records/records.py find --kind todo --status open
python3 /opt/data/skills/personal/records/records.py find --kind event --from <today>
python3 /opt/data/skills/personal/records/records.py find --kind travel
python3 /opt/data/skills/personal/records/records.py update <id> --status done
```

Trips drive the timezone: to correct one, set the travel record's status to `cancelled` or fix
its dates; the next run recomputes the timezone. `email_watch.py zone` recomputes it now.
