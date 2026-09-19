"""Private operator-only migration of inspected cron fingerprints; never grants new modes."""
import copy
import hashlib
import json
from pathlib import Path

from alfie_permissions import job_digest

LEGACY_FIELDS = ('id', 'name', 'prompt', 'script', 'no_agent', 'origin', 'deliver',
                 'failure_deliver', 'workdir', 'model', 'provider', 'skills', 'enabled_toolsets',
                 'disabled_toolsets', 'precheck', 'wakeAgent')


def migrate(policy, jobs):
    result = copy.deepcopy(policy)
    if len(jobs) != len(policy['jobs']) or {str(j['id']) for j in jobs} != set(policy['jobs']):
        raise ValueError('Job inventory changed; inspect before migration')
    for job in jobs:
        record = result['jobs'][str(job['id'])]
        old = hashlib.sha256(json.dumps({k: job.get(k) for k in LEGACY_FIELDS},
            sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if record['digest'] != old:
            raise ValueError('Reviewed definition changed; migration denied')
        if any(job.get(k) for k in ('context_from', 'monitor_script', 'monitor_url',
                                    'base_url', 'skill', 'skills', 'attach_to_session')):
            raise ValueError('Additional execution input requires separate review')
        if not isinstance(job.get('schedule'), dict) or job['schedule'].get('kind') not in ('once', 'interval'):
            raise ValueError('Uninspected schedule type')
        if record.get('mode') not in ('chat', 'blocked', 'reviewed-script'):
            raise ValueError('Uninspected grant type')
        for filename, digest in record.get('files', {}).items():
            if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != digest:
                raise ValueError('Scheduled code drift')
        record['digest'] = job_digest(job)
    result['version'] = 2
    return result


if __name__ == '__main__':
    from cron.jobs import list_jobs
    policy = json.loads(Path('/opt/alfie-permissions/cron-policy.json').read_text())
    print(json.dumps(migrate(policy, list_jobs(include_disabled=True)), sort_keys=True))
