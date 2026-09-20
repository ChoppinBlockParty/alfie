"""Narrow reminder management; never exposes general cron administration."""
import json

SCHEMA = {
    'name': 'reminder',
    'description': ('Create, list, pause or resume owner-only reminders. Cancellation uses pause. Reminders run '
                    'without tools and deliver only to the originating owner chat. This tool cannot '
                    'schedule scripts, web/account work, alternate destinations or chained jobs.'),
    'parameters': {
        'type': 'object',
        'properties': {
            'action': {'type': 'string', 'enum': ['create', 'list', 'pause', 'resume']},
            'text': {'type': 'string', 'description': 'Reminder text; required for create.'},
            'schedule': {'type': 'string', 'description': "For example 'in 30m', 'tomorrow at 9am', or 'every monday 9am'."},
            'name': {'type': 'string', 'description': 'Optional short label.'},
            'repeat': {'type': 'integer', 'description': 'Optional bounded repeat count.'},
            'job_id': {'type': 'string', 'description': 'Required for pause, resume or remove; obtain it with list.'},
        },
        'required': ['action'],
    },
}


def _owned_reminders():
    from alfie_permissions import current, safe_reminder_job
    from cron.jobs import list_jobs

    grant = current()
    owner = {'user': grant.owner, 'chat': grant.chat}
    return [job for job in list_jobs(include_disabled=True) if safe_reminder_job(job, owner)]


def _summary(job):
    from alfie_permissions import REMINDER_NAME, REMINDER_PROMPT
    return {
        'id': str(job.get('id') or ''),
        'name': str(job.get('name') or '')[len(REMINDER_NAME):],
        'text': str(job.get('prompt') or '')[len(REMINDER_PROMPT):],
        'schedule': job.get('schedule_display') or job.get('schedule'),
        'state': job.get('state'),
        'next_run_at': job.get('next_run_at'),
        'repeat': (job.get('repeat') or {}).get('times'),
    }


def reminder(action='', text='', schedule='', name='', repeat=None, job_id='', **_):
    from alfie_permissions import authorize, Denied, REMINDER_NAME, REMINDER_PROMPT
    args = {'action': action}
    for key, value in (('text', text), ('schedule', schedule), ('name', name),
                       ('repeat', repeat), ('job_id', job_id)):
        if value not in ('', None):
            args[key] = value
    try:
        authorize('reminder', args)
    except Denied as exc:
        return json.dumps({'error': str(exc)})

    from tools.cronjob_tools import cronjob
    if action == 'list':
        return json.dumps({'reminders': [_summary(job) for job in _owned_reminders()]}, ensure_ascii=False)
    if action == 'create':
        label = (name or text.strip().replace('\n', ' ')[:80]).strip()
        return cronjob(action='create', prompt=REMINDER_PROMPT + text.strip(),
                       schedule=schedule.strip(), name=REMINDER_NAME + label,
                       repeat=repeat, deliver='origin', enabled_toolsets=[])
    selected = next((job for job in _owned_reminders() if str(job.get('id')) == job_id), None)
    if selected is None:
        return json.dumps({'error': 'Reminder not found; list reminders and use its exact ID.'})
    return cronjob(action=action, job_id=job_id)


def register(ctx):
    ctx.register_tool(name='reminder', toolset='reminders', handler=lambda args, **_: reminder(**args),
                      description=SCHEMA['description'], schema=SCHEMA, emoji='⏰')
