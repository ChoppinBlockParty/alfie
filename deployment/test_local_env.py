"""Regression: zsh's HOST must never be mistaken for the configured SSH target."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class LocalEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'deployment').mkdir()
        self.loader = self.root / 'deployment/local-env.sh'
        shutil.copyfile(Path(__file__).with_name('local-env.sh'), self.loader)
        (self.root / '.env.local').write_text('ALFIE_VPS_HOST=fixture-remote\n')
        self.env = dict(os.environ, HOST='fixture-ambient')
        for key in ('ALFIE_VPS_HOST', 'ALFIE_LOCAL_ENV_LOADED', 'ALFIE_REPO_ROOT', 'BASH_ENV', 'ENV', 'ZSH_VERSION'):
            self.env.pop(key, None)

    def run_shell(self, shell, code):
        return subprocess.run([shell, '-c', code, 'test', str(self.loader)],
                              env=self.env, capture_output=True, text=True, timeout=5)

    def test_bash_loads_repository_target_not_ambient_host(self):
        result = self.run_shell('/bin/bash', 'source "$1" && printf "%s" "$ALFIE_VPS_HOST"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'fixture-remote')

    def test_zsh_refuses_loader_before_a_following_command(self):
        shell = shutil.which('zsh')
        if not shell:
            self.skipTest('zsh is not installed')
        result = self.run_shell(shell, 'source "$1" && printf "SHOULD_NOT_RUN"')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('requires Bash', result.stderr)
        self.assertEqual(result.stdout, '')

    def test_failed_environment_file_stops_the_caller(self):
        (self.root / '.env.local').write_text('ALFIE_VPS_HOST=fixture-remote\nreturn 1\n')
        result = self.run_shell('/bin/bash', 'source "$1" && printf "SHOULD_NOT_RUN"')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')

    def test_old_host_is_not_a_fallback(self):
        (self.root / '.env.local').write_text('HOST=fixture-old\n')
        result = self.run_shell('/bin/bash', 'source "$1" && printf "SHOULD_NOT_RUN"')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Set ALFIE_VPS_HOST', result.stderr)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
