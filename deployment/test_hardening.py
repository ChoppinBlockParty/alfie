import importlib.util
from pathlib import Path
import subprocess
import unittest

from sandbox_mounts import restricted_mounts
from render import render


class SandboxMountTests(unittest.TestCase):
    def test_private_binds_removed_code_read_only_and_workspace_retained(self):
        mounts = ['/opt/alfie/data/shared:/opt/data/shared:rw',
                  '/opt/alfie/data/auth.json:/tmp/auth.json:ro',
                  '/opt/alfie/data/security:/opt/data/security',
                  '/opt/alfie/data/skills:/opt/data/skills:rw',
                  'sandbox-work:/workspace', '/opt/alfie/ssh/authorized_keys:/keys/authorized_keys:ro']
        result = restricted_mounts(mounts)
        self.assertEqual(result, ['/opt/alfie/data/skills:/opt/data/skills:ro',
                                 'sandbox-work:/workspace', mounts[-1]])

    def test_long_syntax_and_named_shared_mount(self):
        code = {'type': 'bind', 'source': '/opt/alfie/data/scripts', 'target': '/scripts'}
        mounts = [code, {'type': 'volume', 'source': 'shared-data', 'target': '/opt/data/shared'},
                  {'type': 'bind', 'source': '/private/records.db', 'target': '/records'}]
        self.assertEqual(restricted_mounts(mounts), [dict(code, read_only=True)])
        self.assertNotIn('read_only', code)

    def test_broad_and_noncanonical_mounts_fail_closed(self):
        for value in ('/opt/alfie:/host', '/:/host', '/opt/alfie/data/skills/../shared:/data', '/tmp'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                restricted_mounts([value])


class FirewallPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        template = Path(__file__).with_name('firewall.sh').read_text()
        cls.template = template
        script = render(template, {'ALFIE_PUBLIC_IPV4': '192.0.2.10'})
        result = subprocess.run(['sh', '-s', '--', '--print'], input=script,
                                capture_output=True, text=True, check=True)
        cls.rules = result.stdout.splitlines()

    def test_one_transaction_and_no_unrelated_chain_flush(self):
        self.assertEqual(self.rules[0], '*filter')
        self.assertEqual(self.rules[-1], 'COMMIT')
        self.assertEqual(self.rules.count('COMMIT'), 1)
        self.assertEqual([line for line in self.rules if line.startswith('-F ')],
                         ['-F ALFIE-FORWARD', '-F ALFIE-HOST'])
        self.assertNotIn('iptables -F', self.template)
        self.assertLess(self.template.index('--noflush --test'),
                        self.template.index('--noflush <'))

    def test_existing_worker_flows_do_not_bypass_policy(self):
        established = self.rules.index('-A ALFIE-FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN')
        for source in ('172.31.240.3', '172.31.240.4', '172.31.240.5', '172.31.241.2'):
            self.assertLess(self.rules.index(f'-A ALFIE-FORWARD -s {source} -j DROP'), established)
            self.assertIn(f'-A ALFIE-HOST -s {source} -j DROP', self.rules)
        for port in (2222, 8770):
            replies = [r for r in self.rules if f'--sport {port} ' in r]
            self.assertEqual(len(replies), 1)
            self.assertIn('--ctdir REPLY', replies[0])

    def test_unrendered_template_refused_before_commands(self):
        result = subprocess.run(['sh', '-s', '--', '--print'], input=self.template,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
