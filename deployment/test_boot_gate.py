import unittest
from boot_gate import NAMES, check_policies


class BootGateTests(unittest.TestCase):
    def test_only_bounded_non_boot_restart_policies_accepted(self):
        items = [{'Name': '/' + name, 'HostConfig': {'RestartPolicy':
                 {'Name': 'on-failure', 'MaximumRetryCount': 5}}} for name in NAMES]
        check_policies(items)
        for name in ('always', 'unless-stopped', 'no'):
            items[0]['HostConfig']['RestartPolicy']['Name'] = name
            with self.assertRaises(ValueError):
                check_policies(items)
