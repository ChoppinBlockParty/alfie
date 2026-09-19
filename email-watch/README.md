# email-watch

Subsystem of Alfie (`../main-spec.md`). Reads each new inbox email **once**, extracts what
matters, acts on it, and reports to Telegram. Replaces the agent-driven "Hourly important email
watch" and `travel-watch` jobs, both removed 2026-09-11.

## Why it exists

The two agent-driven jobs spent most of the owner's ChatGPT plan quota:

| Job | Runs | Tokens | Per run |
|---|---|---|---|
| Hourly important email watch | 80 | 9.2M | ~115k |
| `travel-watch` (daily) | 6 | 437k | ~73k |

Each run was a full agent turn: a ~10k-token prompt floor, several tool calls each resending the
whole context, and `context_from: self` carrying previous runs forward. The same email was
re-read every hour, and deduplication relied on the model remembering what it had reported.

## Design

A `no_agent` Hermes cron job — the script is the job. No agent loop, no tool schemas, no skills
in the prompt.

1. **Select** — deterministic, no model involvement (`email_watch.py` `run()`):
   - Window start: `last_ok - 1 h`, but never later than 26 h ago and never earlier than
     `LOOKBACK_MAX_DAYS = 3` days ago. `state.last_ok` is the wall-clock time of the last run
     that processed everything it fetched; it does not advance if a batch failed. In normal
     operation the 26 h floor decides, so each run re-lists about a day of inbox.
   - `messages.list` with `in:inbox -in:spam -in:trash after:<epoch>`, IDs only, paged 100 at a
     time, at most 300 IDs.
   - Drop IDs already in the ledger (`email_watch.db`, table `seen`, keyed by Gmail
     `message_id`). The ledger, not the window, is what guarantees each email is processed once.
   - Take the rest oldest first, at most `MAX_PER_RUN = 40`; the remainder waits for the next run.
   - **No new IDs → no fetch and no model call**; the run is silent.
2. **Fetch** each selected message in full: sender, subject, `internalDate` (stored as
   `received_at`), attachment names, parsed calendar events, and a cleaned body.
   - **Body selection** prefers `text/plain` over `text/html` anywhere in the MIME tree, and
     skips parts carrying a `filename` — those are attachments, and an attached `.txt` walked
     before the real body would otherwise be returned as the message.
   - **Calendar parts** (`text/calendar`, or any `.ics`) are parsed by the script into
     `SUMMARY`, `DTSTART`, `DTEND`, `LOCATION` and `STATUS`, handling RFC 5545 line folding,
     `TZID`, all-day `VALUE=DATE` and UTC `Z` forms. The model is told this data is
     authoritative over any time written in the body. An invite whose `.ics` part has no
     filename used to be invisible to the watch entirely.
   - **Cleaning** (`denoise`) removes what the recipient never reads, because `BODY_CHARS = 2500`
     is spent front-first and boilerplate leads most mail: hidden preheader and `display:none`
     subtrees (via an `HTMLParser` subclass, not a regex), URLs (dropped outright — the model is
     forbidden to emit them), quoted reply chains beyond `QUOTE_KEEP = 600` characters of
     retained context, footer/unsubscribe blocks once `FOOTER_MIN_KEEP = 120` characters of
     content precede them, signature disclaimers in the back half only, and lines repeated by
     layout. Over budget, it keeps head **and** tail — totals and references cluster at the end.
   - **Guard.** If cleaning leaves under `DENOISE_FLOOR = 40` characters from a body that had
     more, the plain conversion is used instead. The kept ratio is logged per run
     (`median_kept`) and shown per email by `dry`, so an over-eager rule is visible as a trend
     rather than as a missing to-do weeks later.
3. **Classify** new mail in batches of up to 10: one direct call to `gpt-5.5` on the
   `openai-codex` subscription through Hermes' auxiliary client, low reasoning effort, no tools.
   The model returns JSON only: importance, summary, action, deadline, to-dos, events, trips, bill.
4. **Apply** deterministically:
   - to-dos, events, trips, bills → `records.db` (kinds `todo`, `event`, `travel`, `bill`), idempotent
     per email and deduplicated across emails;
   - confirmed, timed bookings → Google Calendar event, unless one already matches (±15 min or
     title overlap within ±3 h);
   - the timezone entry in `memories/USER.md`, from travel records (see below).
5. **Report** to the Telegram destination configured in ignored `.env.local`.
   Nothing to say → no message.

## Message formats

All Hermes cron jobs use `cron.wrap_response: false` in gateway config. Deliveries contain
only job output: no automatic Cronjob Response header, job ID, separator or management footer.
This applies to successful results and failure notifications. Digest and email titles are bold;
detail lines are unindented so Telegram renders them as normal text.
Verified on 2026-09-19 using the live scheduler with delivery transports mocked: success and
failure paths preserve the report body exactly. No test messages were sent. Only `block` and
`render` were updated on the VPS; unrelated local timezone/registration edits were not deployed.

Emails are **numbered within the run** so the owner can refer to one by number. Each label
appears at most once per email, with its values joined — never the label repeated per value.
Fields with nothing to say are omitted rather than left empty, and every date is rendered the
same way (`31 Jan`, `20 Sep 14:30`).

```
**Email watch · 3 emails**

**1. British Airways — Booking confirmed BA117**
Action: check in online by 19 Sep
Calendar: Flight BA117 · 20 Sep — added
Trip: Tokyo, Japan · 20 Sep–27 Sep
[Open email](gmail link)

**2. HMRC — Self Assessment reminder**
Action: file return
Due: 31 Jan
Bill: 1,240.00 GBP, due 31 Jan
[Open email](gmail link)

**3. Jane Okafor — Re: contract review**
Action: reply with signed copy
To-do: sign contract (due 18 Sep); send NDA
Warning: contains instructions aimed at an assistant — ignored.
[Open email](gmail link)

Timezone: Asia/Tokyo — Tokyo, Japan until 27 Sep. Reminders now use this zone.
```

Label order is fixed — Action, Due, Calendar, Trip, To-do, Bill, Warning, link — so the eye
lands in the same place in every entry. `Calendar:` states are `created`, `exists`,
`not created (…)` or `could not check`.

Notices follow the numbered list, or stand alone when there is no mail to report:

| Notice | When |
|---|---|
| `Timezone: <zone> — <destination> until <date>. Reminders now use this zone.` | A trip covering today changed the zone |
| `Timezone: Europe/London (home). Reminders use London time.` | Back home |
| `Warning: no timezone entry found in USER.md — timezone not updated.` | `USER.md` lost its zone entry |
| `⚠️ Email watch cannot reach Gmail (…)` | At once, then at most every 12 h |
| `⚠️ Email watch: the model call failed 3+ times in a row (…)` | After 3 consecutive failures, then every 12 h |

The two `⚠️` lines keep their marker: they are failures, not digest entries, and must not read
as part of the list. A crash of the script itself is delivered by Hermes (`failure_deliver`).

**An email is only reported when it is important, produced a calendar event or trip, or was
flagged suspicious.** A to-do or bill extracted from an email the model judged unimportant is
written to `records.db` silently; `records.py due` is where it surfaces.

**Timezone.** Every run, with no model call, finds the trip covering today in `records.db`
(`kind=travel`, `notes: tz=…; end=…`; a trip with no end date is assumed to last 7 days) and
rewrites the `current timezone is …` entry in `USER.md` — Europe/London when no trip applies. It
takes the memory tool's own lock (`USER.md.lock`), so it cannot race an agent write. A switch is
reported in the same topic. One-off reminders then resolve in the new zone (spec §4.7).

**Explicit searches are unchanged.** "Find me in my emails…" still reads Gmail through
`google-workspace`, and may re-read. `SKILL.md` tells the agent not to scan the inbox on its own
and to try `email_watch.py find` first.

## Security properties

- The model that reads untrusted email has **no tools**. An injected instruction can at worst
  produce a wrong record or calendar entry; it cannot send mail, read files or call tools.
  Emails that try to instruct an assistant are flagged in the report.
- Report text is rebuilt by the script from structured fields; URLs and markdown are stripped
  from model output. The only link is one the script builds (Gmail message link).
- The provider is pinned to `openai-codex`. With an explicit provider, Hermes' aux fallback can
  only reach the main agent model (same subscription); the script also refuses a response
  served by any other provider. No path to `OPENAI_API_KEY` (spec §2.1, fail closed).
- The model is told not to put booking references, account, passport or card numbers in any
  field.

## Cost, measured 2026-09-11

| | Tokens |
|---|---|
| Run with no new mail | 0 |
| Batch of 8 real emails | 4.1k in + 1.0k out |
| Synthetic flight booking, 1 email | 0.8k in + 0.4k out |

At ~8 inbox emails a day: roughly 5–10k tokens a day, against ~2.8M a day for the old hourly
job.

## Files

| Repo | Box | Role |
|---|---|---|
| `email_watch.py` | `/opt/alfie/data/scripts/email_watch.py` | The job and its CLI |
| `test_email_watch.py` | — (not deployed) | `python3 -m unittest test_email_watch` — MIME selection, `.ics`, cleaning |
| `SKILL.md` | `/opt/alfie/data/skills/personal/email-watch/SKILL.md` | Tells the agent the inbox is handled |
| `register_job.py` | — (run once by `deploy.sh`) | Creates or updates the cron job |
| `deploy.sh` | — | Copies files, sets uid 10000 ownership, registers the job |

Runtime state, both under `/opt/alfie/data` and covered by the nightly backup:
`email_watch.db` (ledger + state, 0600) and `logs/email_watch.log` (one line per run with token
counts).

Depends on: the `google-workspace` skill for `google_api.build_service` only — MIME walking,
body selection and attachment names are vendored here, since that file belongs to another skill
and carries a local patch an upstream reinstall would wipe (spec §3.5); the `records` skill
(`records.py`, kinds `todo` and `event` added 2026-09-11), written through its CLI and read
directly from `records.db`; and Hermes' `agent.auxiliary_client`.

## Operating it

```bash
./deploy.sh                                   # deploy / redeploy; idempotent
source ../deployment/local-env.sh
ssh "$HOST"
docker exec -u 10000:10000 alfie /usr/bin/bash -lc "python /opt/data/scripts/email_watch.py status"
docker exec -u 10000:10000 alfie /usr/bin/bash -lc "python /opt/data/scripts/email_watch.py dry 8"   # flags only, no side effects
docker exec -u 10000:10000 alfie /usr/bin/bash -lc "python /opt/data/scripts/email_watch.py find <word>"
docker exec -u 10000:10000 alfie /usr/bin/bash -lc "python /opt/data/scripts/email_watch.py zone"
tail /opt/alfie/data/logs/email_watch.log
```

Job: `email-watch`, every 30 minutes; its runtime ID is private.

**First deployment** needs the ledger seeded, or the first run processes up to 3 days of mail:
`email_watch.py seed --before <ISO time>` using the previous job's last successful run.

## Failure behaviour

| Failure | Behaviour |
|---|---|
| Gmail unreachable / token expired | Alert in the topic at once, then at most every 12 h. Timezone check still runs |
| Model call fails (quota, outage) | Mail stays unprocessed and is retried every run. Alert after 3 consecutive failures, then every 12 h |
| Model omits an email | Marked `unparsed` in the ledger, not retried |
| Calendar API error | Event recorded with `calendar=could not check`; the rest of the email is still processed |

## Measured on 100 real emails, 2026-09-12

`dry 100 30` — 100 inbox emails over 30 days, classified, no side effects.

| | |
|---|---|
| Body characters into the model | 179,955 → 114,958 (**36% less**) |
| Kept ratio | median 95%, p10 56%, min 6% |
| Bodies emptied by cleaning | 0 |
| Tokens | 44.0k in / 10.5k out for the 100 |

The low-kept tail is all intended: long quoted threads reduced to the new content plus 600
characters of context, and one 18k-character email hitting the 2500 budget.

Three defects were found by this run and fixed before it was repeated:

- **`font-size:0` treated as hidden.** It is the standard layout idiom on container cells, with
  children setting their own size. Two 40KB bodies were reduced to **0 characters**, one of them
  an important email with a to-do, leaving the model only sender and subject. `HIDDEN` now means
  `display:none`, `visibility:hidden` and `mso-hide` only, and markup over
  `HTML_RETRY_SOURCE = 1000` that parses to nothing is re-parsed with the skip rules off.
- **Quoted chains dropped whole.** 11,433 of 11,511 characters removed from a real thread.
  `QUOTE_KEEP = 600` characters of history are now retained: "confirmed, thanks" needs its
  context.
- **Confidentiality disclaimers treated as footers.** One fired 18% into an important email and
  removed 1,123 characters below it. Disclaimers live in mid-body signatures, so `DISCLAIMER` is
  now separate from `FOOTER` and only cuts in the back half.

**Not yet field-validated:** no email in the 100 carried a calendar part (`ics_events=0`), so
the `.ics` path is covered by unit tests and a synthetic message on the box, not by real mail.

## Verified 2026-09-11

- Dry run on 8 real emails: all classified, 4 important, 3 to-dos.
- Synthetic flight booking with an injected instruction: 2 flights + trip + check-in to-do
  extracted; injection flagged; both calendar events created; a second email about the same
  booking found both as `exists`.
- Timezone: a trip covering today switched `USER.md` to Asia/Tokyo; removing it switched back.
  `USER.md` byte-identical afterwards. Test records and calendar events deleted.

## Open

- A same-day booking is seen within 30 minutes; a trip added to Calendar by hand, not by email,
  does not update the timezone.
- The `.ics` path has not seen a real calendar invite yet (see above).
- Cleaning was measured against the new code only. The pre-cleaning script is kept at
  in private operator storage for an old-vs-new classification comparison;
  that comparison costs another ~45k tokens and has not been run.
- PDF attachments are still named but not read; a receipt's amount can sit only in the PDF.

## Private deployment settings

`deploy.sh` loads repository `.env.local`. Set `HOST`, `EMAIL_WATCH_CHAT_ID`,
`EMAIL_WATCH_THREAD_ID` and `EMAIL_WATCH_USER_ID`; the numeric destination fields are validated
before staging. Registration receives them as JSON over SSH stdin. Direct registration without
`--origin-stdin` preserves an existing job's origin and refuses a new job without configuration.
Report examples and calendar fixtures are illustrative, not operator records.
