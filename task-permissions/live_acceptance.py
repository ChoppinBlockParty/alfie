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
                ('browse', {'action': 'fill', 'value': 'Never transmit'}),
                ('browse', {'action': 'click', 'ref': 'synthetic'}),
            ):
                result = json.loads(registry.dispatch(tool, args))
                assert result.get('error'), (mode, tool)
            if mode == 'email-read':
                result = json.loads(registry.dispatch('google_workspace', {'operation': 'gmail.labels', 'arguments': {}}))
                assert isinstance(result, dict) and result.get('error')
            else:
                result = json.loads(registry.dispatch('google_workspace', {'operation': 'gmail.labels', 'arguments': {}}))
                assert result.get('error')
        finally:
            CURRENT.reset(token)
    print('PASS email/web tasks deny sends, memory, cron, shell, fill and click; unreviewed private reads denied')
    result = json.loads(registry.dispatch('google_workspace', {'operation': 'gmail.labels', 'arguments': {}}))
    assert result.get('error')
    print('PASS absent task context cannot read Google')


if __name__ == '__main__':
    main()
