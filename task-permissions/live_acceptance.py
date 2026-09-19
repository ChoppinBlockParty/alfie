"""Run inside gateway. Unauthorized effects and private reads must remain blocked."""
import json
from pathlib import Path
import time
import uuid
from alfie_permissions import CURRENT, Grant
from hermes_cli.plugins import discover_plugins
from tools.registry import registry


def main():
    discover_plugins()
    owner = json.loads(Path('/opt/data/plugins/google_workspace/approval-policy.json').read_text())
    for mode in ('email-read', 'web-read'):
        token = CURRENT.set(Grant(uuid.uuid4().hex, mode, owner['user'], owner['chat'],
                                  'operator-acceptance', 'synthetic', 'Synthetic acceptance', time.time() + 60))
        try:
            for tool, args in (
                ('google_workspace', {'operation': 'gmail.send', 'arguments': {'to': 'recipient@example.com', 'subject': 'Synthetic', 'body': 'Never send'}}),
                ('memory', {'action': 'add', 'content': 'Never persist'}),
                ('cronjob_manage', {'action': 'create'}),
                ('terminal', {'command': 'false'}),
                ('browse', {'action': 'evaluate'}),
            ):
                result = json.loads(registry.dispatch(tool, args))
                assert result.get('error'), (mode, tool)
            if mode == 'email-read':
                # A disposable docker-exec process has no live Telegram adapter bridge;
                # verify policy authorization here. The operator health probe owns API health.
                from alfie_permissions import authorize
                authorize('google_workspace', {'operation': 'gmail.labels', 'arguments': {}})
            else:
                result = json.loads(registry.dispatch('google_workspace', {'operation': 'gmail.labels', 'arguments': {}}))
                assert result.get('error')
                # Authorization only: do not start a live browser from this denial probe.
                from alfie_permissions import authorize
                authorize('browse', {'action': 'open'})
        finally:
            CURRENT.reset(token)
    print('PASS email/web tasks deny sends, memory, cron, shell and unknown browser actions; bounded read/browser paths work')
    result = json.loads(registry.dispatch('google_workspace', {'operation': 'gmail.labels', 'arguments': {}}))
    assert result.get('error')
    print('PASS absent task context cannot read Google')


if __name__ == '__main__':
    main()
