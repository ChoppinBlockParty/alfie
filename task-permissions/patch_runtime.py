"""Generate mandatory hooks from an inspected Hermes tree, never edit upstream in place."""
import ast
import hashlib
import json
from pathlib import Path
import sys


def prepend_body(source, function, code, *, class_name=None, decorator=None):
    tree = ast.parse(source)
    scope = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name) if class_name else tree
    matches = [n for n in scope.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == function]
    if len(matches) != 1:
        raise ValueError('Pinned function shape changed: ' + function)
    node = matches[0]
    lines = source.splitlines(keepends=True)
    if decorator:
        lines.insert(node.lineno - 1, ' ' * node.col_offset + '@' + decorator + '\n')
    else:
        body = node.body[1:] if isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str) else node.body
        start = body[0]
        lines.insert(start.lineno - 1, ''.join(' ' * start.col_offset + s + '\n' for s in code.splitlines()))
    result = ''.join(lines)
    compile(result, '<patched>', 'exec')
    return result


def patch(relative, source):
    if 'ALFIE_MANDATORY_TASK_POLICY' in source:
        raise ValueError('Expected pristine pinned source')
    if relative == 'tools/registry.py':
        source = prepend_body(source, 'dispatch',
            'from alfie_permissions import authorize, Denied\ntry:\n    authorize(name, args, charge=True)\nexcept Denied as exc:\n    return tool_error(str(exc))', class_name='ToolRegistry')
    elif relative == 'model_tools.py':
        # Each task exposes at most one connector. Its concrete schema must remain
        # visible: the generic discovery bridge is intentionally not authorized.
        source = prepend_body(source, 'get_tool_definitions',
                              'skip_tool_search_assembly = True')
        source = prepend_body(source, 'handle_function_call',
            'from alfie_permissions import authorize, Denied\ntry:\n    authorize(function_name, function_args)\nexcept Denied as exc:\n    return tool_error(str(exc))')
    elif relative == 'gateway/run_inbound.py':
        source = prepend_body(source, '_handle_message', '', class_name='GatewayInboundMixin',
                              decorator='__import__("alfie_permissions").gateway_entry')
    elif relative == 'cron/scheduler.py':
        source = prepend_body(source, 'run_job', '', decorator='__import__("alfie_permissions").cron_entry')
    elif relative == 'run_agent.py':
        anchor = '        from agent.agent_init import init_agent\n        init_agent(self, **init_kwargs)'
        if source.count(anchor) != 1:
            raise ValueError('Agent initialization shape changed')
        source = source.replace(anchor, '        from alfie_permissions import agent_settings\n'
                                '        init_kwargs = agent_settings(init_kwargs)\n' + anchor)
    elif relative == 'agent/system_prompt.py':
        source = prepend_body(source, 'build_system_prompt',
                              'from alfie_permissions import system_prompt\nreturn system_prompt()')
    elif relative == 'agent/conversation_loop.py':
        source = prepend_body(source, 'run_conversation',
            'from alfie_permissions import current, system_prompt\n'
            'grant = current()\nuser_message = grant.brief\nconversation_history = []\n'
            'system_message = system_prompt()\nmoa_config = {}\n'
            'agent._cached_system_prompt = None\nagent._gateway_turn_context_notes = ""')
    elif relative == 'gateway/run_turn_runner.py':
        anchor = '        if not (cache_lock and cache is not None):\n'
        if source.count(anchor) != 1:
            raise ValueError('Cache shape changed')
        source = source.replace(anchor,
            '        if cache_lock and cache is not None:\n'
            '            with cache_lock:\n'
            '                out.evicted = self._pop_cached_agent_for_eviction()\n'
            '        return out  # Task scopes never reuse cached agents\n' + anchor, 1)
    elif relative == 'gateway/run_turn.py':
        start = source.index('        history = await self._hmwa_run_session_hygiene(')
        end = source.index('        await self._hmwa_first_contact_notes', start)
        source = source[:start] + '        history = []  # Fresh task; never run a historical hygiene agent\n\n' + source[end:]
        # No auto-loaded skills or quoted/replied/vision context enters task classification.
        source = source.replace('        _auto = getattr(event, "auto_skill", None)', '        _auto = None')
    elif relative == 'plugins/platforms/telegram/adapter.py':
        old = 'self._disable_link_previews: bool = self._coerce_bool_extra("disable_link_previews", False)'
        if source.count(old) != 1:
            raise ValueError('Telegram preview configuration shape changed')
        source = source.replace(old, 'self._disable_link_previews: bool = True')
        old = 'disable_link_previews = bool(getattr(pconfig, "extra", {}) and pconfig.extra.get("disable_link_previews"))'
        if source.count(old) != 1:
            raise ValueError('Telegram delivery preview shape changed')
        source = source.replace(old, 'disable_link_previews = True')
    else:
        raise ValueError('Unknown patch target')
    source += '\n# ALFIE_MANDATORY_TASK_POLICY\n'
    compile(source, relative, 'exec')
    return source


TARGETS = ('tools/registry.py', 'model_tools.py', 'gateway/run_inbound.py', 'cron/scheduler.py', 'run_agent.py',
           'agent/system_prompt.py', 'agent/conversation_loop.py', 'gateway/run_turn_runner.py',
           'gateway/run_turn.py', 'plugins/platforms/telegram/adapter.py')


if __name__ == '__main__':
    root, out = map(Path, sys.argv[1:])
    manifest = {}
    for relative in TARGETS:
        source = (root / relative).read_text()
        result = patch(relative, source)
        manifest[relative] = {'baseline': hashlib.sha256(source.encode()).hexdigest(),
                              'patched': hashlib.sha256(result.encode()).hexdigest()}
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result)
    (out / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2))
    print('Mandatory runtime hooks generated and syntax checked.')
