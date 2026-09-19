"""Installed-runtime schema checks; no model, Telegram or Google API requests.

Optionally evaluate a staged model_tools.py in this disposable process before cutover.
"""
from pathlib import Path
import sys
import time

import alfie_permissions as policy
import model_tools

if len(sys.argv) == 2:
    source = Path(sys.argv[1]).read_text()
    exec(compile(source, 'model_tools.py', 'exec'), model_tools.__dict__)

from unittest.mock import patch
from tools import tool_search

for mode in policy.MODES:
    token = policy.CURRENT.set(policy.Grant('schema-' + mode, mode, '123', '-1001',
                                          'operator-test', '1', 'Synthetic', time.time() + 60))
    try:
        settings = policy.agent_settings({})
        for quiet in (False, True, True):
            with patch.object(tool_search, 'assemble_tool_defs', side_effect=AssertionError('Discovery assembly invoked')) as assembly:
                definitions = model_tools.get_tool_definitions(
                    enabled_toolsets=settings['enabled_toolsets'],
                    disabled_toolsets=settings['disabled_toolsets'], quiet_mode=quiet)
                assembly.assert_not_called()
            expected = {'research'} if mode == 'web-read' else {'google_workspace'} if policy.MODES[mode] else set()
            assert {d['function']['name'] for d in definitions} == expected, mode
            for definition in definitions:
                params = definition['function']['parameters']
                assert params.get('properties'), mode
                if definition['function']['name'] == 'google_workspace':
                    assert policy.MODES[mode] <= set(params['properties']['operation']['enum']), mode
        for name in ('tool_search', 'tool_describe', 'tool_call', 'terminal', 'browse', 'memory'):
            try:
                policy.authorize(name, {})
            except policy.Denied:
                pass
            else:
                raise AssertionError('Unexpected helper/effect permission')
    finally:
        policy.CURRENT.reset(token)
print('PASS all task modes expose concrete connector schemas without discovery; helper/effect denials retained')
