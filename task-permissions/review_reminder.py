"""Operator-only private policy rendering for an inspected, tool-free reminder.

Run inside the gateway with --job-id from private operator inventory. Redirect stdout to
a private staging file; it contains deployment identifiers. Never install while running.
This does not run the reminder or change the scheduler definition.
"""
import argparse
import copy
import json
from pathlib import Path

from alfie_permissions import job_digest


def review(policy, jobs, job_id, owner):
    result = copy.deepcopy(policy)
    matches = [job for job in jobs if str(job.get('id')) == job_id]
    if len(matches) != 1:
        raise ValueError('Expected one reviewed job')
    job = matches[0]
    record = result['jobs'].get(job_id)
    if not record or record.get('digest') != job_digest(job) or record.get('mode') != 'blocked':
        raise ValueError('Job changed or not blocked; inspect again')
    if job.get('enabled') is not True or job.get('state') != 'scheduled':
        raise ValueError('Never reactivate completed or disabled jobs')
    if any(job.get(key) for key in ('script', 'no_agent', 'precheck', 'monitor_script',
                                   'monitor_url', 'context_from', 'skill', 'skills', 'base_url')):
        raise ValueError('Reminder has additional execution inputs; separate review required')
    origin = job.get('origin') or {}
    if origin.get('platform') != 'telegram' or str(origin.get('user_id')) != owner['user'] \
            or str(origin.get('chat_id')) not in (owner['user'], owner['chat']) \
            or job.get('deliver') != 'origin':
        raise ValueError('Reminder destination is not the fixed owner')
    record['mode'] = 'chat'
    record['review'] = 'operator-reviewed-tool-free-reminder'
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job-id', required=True)
    args = parser.parse_args()
    from cron.jobs import list_jobs
    policy = json.loads(Path('/opt/alfie-permissions/cron-policy.json').read_text())
    owner = json.loads(Path('/opt/data/plugins/google_workspace/approval-policy.json').read_text())
    print(json.dumps(review(policy, list_jobs(include_disabled=True), args.job_id, owner), sort_keys=True))
