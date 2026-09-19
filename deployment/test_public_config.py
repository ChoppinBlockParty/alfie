import importlib.util
from pathlib import Path
import unittest
import contextlib
import io
import json
import runpy
import sys
import types
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('render', Path(__file__).with_name('render.py'))
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)


class PublicConfigTests(unittest.TestCase):
    def test_address_templates_keep_host_denials(self):
        root = Path(__file__).resolve().parent.parent
        env = {'ALFIE_PUBLIC_IPV4': '192.0.2.10', 'ALFIE_PUBLIC_IPV6': '2001:db8::10'}
        for name in ('deployment/firewall.sh', 'deployment/verify.py', 'egress/squid.conf'):
            text = render.render((root / name).read_text(), env)
            self.assertNotIn('@@ALFIE_PUBLIC_', text)
            self.assertIn('192.0.2.10', text)
        self.assertIn('2001:db8::10/128', render.render((root / 'egress/squid.conf').read_text(), env))

    def test_reject_missing_wrong_family_and_injection(self):
        for value in ('', '::1', '192.0.2.10; id', '192.0.2.10/32', 'example.com'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                render.render('@@ALFIE_PUBLIC_IPV4@@', {'ALFIE_PUBLIC_IPV4': value})


class RegistrationTests(unittest.TestCase):
    def run_registration(self, jobs, values=None):
        module = types.ModuleType('cron.jobs')
        module.list_jobs = Mock(return_value=jobs)
        module.create_job = Mock(return_value={'id': 'fixture'})
        module.update_job = Mock(return_value={'id': 'fixture'})
        args = ['register_job.py'] + ([] if values is None else ['--origin-stdin'])
        script = Path(__file__).resolve().parent.parent / 'email-watch/register_job.py'
        with patch.dict(sys.modules, {'cron': types.ModuleType('cron'), 'cron.jobs': module}), \
             patch.object(sys, 'argv', args), patch.object(sys, 'stdin', io.StringIO(json.dumps(values))), \
             contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(script), run_name='__main__')
        return module

    def test_existing_destination_preserved(self):
        origin = {'platform': 'telegram', 'chat_id': '-100', 'user_id': '200'}
        module = self.run_registration([{'name': 'email-watch', 'id': 'fixture', 'origin': origin}])
        self.assertEqual(module.update_job.call_args.args[1]['origin'], origin)
        module.create_job.assert_not_called()

    def test_new_job_requires_destination(self):
        with self.assertRaises(SystemExit):
            self.run_registration([])

    def test_stdin_destination_and_validation(self):
        values = {'EMAIL_WATCH_CHAT_ID': '-100', 'EMAIL_WATCH_THREAD_ID': '3',
                  'ALFIE_OWNER_TELEGRAM_USER_ID': '200'}
        module = self.run_registration([], values)
        self.assertEqual(module.create_job.call_args.kwargs['origin']['chat_id'], '-100')
        for bad in ('', 'wrong', '200; id'):
            with self.subTest(bad=bad), self.assertRaises(SystemExit):
                self.run_registration([], dict(values, ALFIE_OWNER_TELEGRAM_USER_ID=bad))


if __name__ == '__main__':
    unittest.main()
