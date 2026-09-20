"""Bounded task-local private reads for an authenticated owner task.

Private reads may span Google services because their results can only return to the owner and the
task has no public or mutating tools. Each distinct selector remains bounded, cached and counted;
failed selectors cannot be retried inside the task.
"""
import json
import threading
import time

MAX_TASKS = 32
MAX_RESULTS = 20
MAX_BYTES = 256 * 1024
MAX_SELECTORS = 8
_states = {}
_lock = threading.Lock()


def canonical(operation, arguments):
    args = dict(arguments)
    if operation in ('gmail.search', 'drive.search', 'calendar.list', 'contacts.list'):
        args.setdefault('max', MAX_RESULTS)
        if type(args['max']) is not int or not 1 <= args['max'] <= MAX_RESULTS:
            raise ValueError('Private reads allow at most 20 results per task')
    if operation == 'calendar.list':
        args.setdefault('calendar', 'primary')
    return args, json.dumps([operation, args], sort_keys=True, ensure_ascii=True, allow_nan=False)


def run(operation, arguments, execute):
    from alfie_permissions import authorize, current
    grant = authorize('google_workspace', {'operation': operation, 'arguments': arguments})
    if grant.source != 'telegram':
        raise ValueError('Private reads require a fresh authenticated owner task')
    args, selector = canonical(operation, arguments)
    with _lock:
        for key, state in list(_states.items()):
            if state['grant'].expires <= time.time():
                del _states[key]
        if grant.task not in _states:
            if len(_states) >= MAX_TASKS:
                raise ValueError('Private read capacity reached')
            _states[grant.task] = dict(grant=grant, lock=threading.Lock(), cache={}, size=0)
        state = _states[grant.task]
    with state['lock']:
        if state['grant'] != current():
            raise ValueError('Read task identity changed')
        if selector in state['cache']:
            return state['cache'][selector]
        if len(state['cache']) >= MAX_SELECTORS:
            raise ValueError('Private read selector budget exhausted; start a new task')
        # Reserve before execution: failure cannot trigger an automatic retry or new search.
        state['cache'][selector] = json.dumps({'error': 'Read outcome unavailable; start a new task'})
        if state['size'] >= MAX_BYTES:
            raise ValueError('Private task output budget exhausted')
        result = execute(operation, args)
        if not isinstance(result, str) or len(result.encode()) + state['size'] > MAX_BYTES:
            raise ValueError('Private task output budget exhausted')
        if operation in ('gmail.search', 'drive.search'):
            rows = [] if result.strip() == 'No messages found.' else json.loads(result)
            if not isinstance(rows, list) or len(rows) > args['max'] or any(
                    not isinstance(row, dict) or not isinstance(row.get('id'), str) or
                    not row['id'] or len(row['id']) > 256 for row in rows):
                raise ValueError('Search result schema invalid; no resource IDs granted')
        state['size'] += len(result.encode())
        state['cache'][selector] = result
        return result
