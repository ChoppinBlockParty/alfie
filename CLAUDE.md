# Alfie - Personal AI agent

This is a project to build, update and maintain persona AI agent, called Alfie.

main-spec.md is the current specification of the project and its status plan. It holds current state only; history lives in git.
plan-next.md is the executable plan for the next build.

Each subsystem is a subproject directory (first: `email-watch/`) with its own README (authoritative for its internals), sources and `deploy.sh`. Change a subsystem there, then deploy; main-spec.md keeps only how it fits the whole.

## Core Instructions

* Be concise and clear. Keep answers short unless asked to be comprehensive.
* Technical tone. No metaphors, idioms or filler.
* Ask a follow-up question when something is ambiguous instead of guessing.
* Separate what you verified by reading code or the box from what you inferred.
* Commit messages: one short line, no body unless asked. Never add `Co-Authored-By`,
  `Claude-Session` or other attribution trailers.
* Treat this repository as public. Never add real secrets, credentials, API/OAuth tokens,
  private or public keys, personal identifiers, account IDs, email addresses, usernames,
  public host IP addresses, instance IDs, SSH aliases, sensitive host paths, backup names,
  or other deployment-specific identifiers. Use obvious placeholders or environment variables.
* Before committing, scan both staged changes and newly added files for sensitive information.
  Run `python3 deployment/check_sensitive.py` and `python3 deployment/check_sensitive.py --staged`.
  If a real value is required for deployment, keep it in an ignored local file or external
  secret store and document only its variable name and expected format.

## Explaining code and algorithms

* Go step by step, in the order the code runs.
* Use the names that are in the code — variables, constants, functions, tables, files — and cite
  `file:line`. Do not invent a name, a helper or a concept the code does not contain; if an
  expression has no name, quote the expression and explain it term by term.
* Give concrete values and ranges, not abstractions: what the constant is set to, what the
  window actually spans in normal operation, what the default is when a value is missing.
* For each step say what it protects against, and name the case it does not cover.
