"""Read-only/offline checks inside installed Hermes; no model, Telegram or Google calls."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from unittest.mock import Mock, patch

import alfie_permissions as permissions


def verify(root):
    manifest = json.loads((root / 'manifest.json').read_text())
    for relative, hashes in manifest.items():
        live = Path('/opt/hermes') / relative
        if hashlib.sha256(live.read_bytes()).hexdigest() not in (hashes['baseline'], hashes['patched']):
            raise ValueError('Installed source drift: ' + relative)
        compile((root / relative).read_text(), relative, 'exec')
    print('PASS pinned source fingerprints and overlay syntax')
    # Run the actual patched registry module in this disposable verification process.
    import tools.registry as registry_module
    exec(compile((root / 'tools/registry.py').read_text(), 'tools/registry.py', 'exec'), registry_module.__dict__)
    registry = registry_module.ToolRegistry()
    handler = Mock(return_value='{}')
    registry.register(name='google_workspace', toolset='google_workspace', schema={}, handler=handler)
    registry.register(name='memory', toolset='memory', schema={}, handler=handler)
    denied = registry.dispatch('google_workspace', {'operation': 'gmail.send'})
    assert 'error' in json.loads(denied)
    token = permissions.CURRENT.set(permissions.Grant('verify', 'email-read', '123', '123',
                                                     'telegram', '1', 'Synthetic', time.time() + 60))
    try:
        assert 'error' in json.loads(registry.dispatch('google_workspace', {'operation': 'gmail.send'}))
        assert 'error' in json.loads(registry.dispatch('memory', {'action': 'add'}))
        handler.assert_not_called()
        assert registry.dispatch('google_workspace', {'operation': 'gmail.get'}) == '{}'
        handler.assert_called_once()
    finally:
        permissions.CURRENT.reset(token)
    print('PASS real patched registry denies absent grants, email writes and memory writes')
    # Check actual public-task agent construction before client initialization.
    import run_agent
    exec(compile((root / 'run_agent.py').read_text(), 'run_agent.py', 'exec'), run_agent.__dict__)
    token = permissions.CURRENT.set(permissions.Grant('verify-public', 'web-read', '123', '123',
                                                     'telegram', '2', 'Public question', time.time() + 60))
    try:
        with patch('agent.agent_init.init_agent') as init:
            run_agent.AIAgent(enabled_toolsets=['hermes-telegram'], prefill_messages=[{'content': 'Private'}])
        opts = init.call_args.kwargs
        assert opts['skip_memory'] and opts['skip_background_review'] and opts['skip_context_files']
        assert opts['prefill_messages'] is None and opts['enabled_toolsets'] == ['websearch']
    finally:
        permissions.CURRENT.reset(token)
    print('PASS real agent constructor removes private context sources and unrelated tools')


if __name__ == '__main__':
    verify(Path(sys.argv[1]))
