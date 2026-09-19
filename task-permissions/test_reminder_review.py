import copy
import unittest

import alfie_permissions as policy
from review_reminder import review


class ReminderReviewTests(unittest.TestCase):
    def setUp(self):
        self.job = {'id': 'synthetic', 'prompt': 'Remind me about the synthetic task',
                    'enabled': True, 'state': 'scheduled', 'deliver': 'origin',
                    'origin': {'platform': 'telegram', 'user_id': '123', 'chat_id': '-1001'}}
        self.owner = {'user': '123', 'chat': '-1001'}
        self.policy = {'jobs': {'synthetic': {'digest': policy.job_digest(self.job),
                                           'mode': 'blocked', 'files': {}}}}

    def test_only_selected_scope_changes_not_scheduler_or_original_policy(self):
        original = copy.deepcopy(self.policy)
        result = review(self.policy, [self.job], 'synthetic', self.owner)
        self.assertEqual(result['jobs']['synthetic']['mode'], 'chat')
        self.assertEqual(self.policy, original)
        self.assertEqual(result['jobs']['synthetic']['digest'], policy.job_digest(self.job))

    def test_changed_disabled_completed_or_extra_execution_inputs_rejected(self):
        for change in ({'prompt': 'Changed'}, {'enabled': False}, {'state': 'completed'},
                       {'monitor_url': 'https://example.com'}, {'context_from': 'another-task'},
                       {'base_url': 'https://example.com'}, {'skill': 'anything'},
                       {'script': 'anything'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                review(self.policy, [dict(self.job, **change)], 'synthetic', self.owner)

    def test_untrusted_destination_or_missing_job_rejected(self):
        with self.assertRaises(ValueError):
            review(self.policy, [], 'synthetic', self.owner)
        job = dict(self.job, origin={'platform': 'telegram', 'user_id': '999', 'chat_id': '-1001'})
        self.policy['jobs']['synthetic']['digest'] = policy.job_digest(job)
        with self.assertRaises(ValueError):
            review(self.policy, [job], 'synthetic', self.owner)
