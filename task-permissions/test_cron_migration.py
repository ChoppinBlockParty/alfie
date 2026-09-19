import hashlib
import json
import unittest
from migrate_cron_policy import migrate, LEGACY_FIELDS
from alfie_permissions import job_digest


class MigrationTests(unittest.TestCase):
    def test_preserves_grants_and_rejects_changed_or_additional_inputs(self):
        job = {'id': 'fixture', 'prompt': 'Synthetic', 'schedule': {'kind': 'once'}, 'enabled': True}
        digest = hashlib.sha256(json.dumps({k: job.get(k) for k in LEGACY_FIELDS},
            sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        policy = {'version': 1, 'jobs': {'fixture': {'digest': digest, 'mode': 'chat', 'files': {}}}}
        result = migrate(policy, [job])
        self.assertEqual(result['jobs']['fixture']['mode'], 'chat')
        self.assertEqual(result['jobs']['fixture']['digest'], job_digest(job))
        self.assertEqual(policy['jobs']['fixture']['digest'], digest)
        for changes in ({'prompt': 'changed'}, {'context_from': ['other']}, {'base_url': 'https://example.com'},
                        {'monitor_script': 'fixture.py'}, {'schedule': {'kind': 'new'}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                migrate(policy, [dict(job, **changes)])
