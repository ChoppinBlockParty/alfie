"""Render private owner bindings to a pipe; never redirect into the public checkout."""
import json
import os
import sys


def policy():
    values = {key: os.environ.get(name, '') for key, name in (
        ('user', 'ALFIE_OWNER_TELEGRAM_USER_ID'), ('chat', 'ALFIE_APPROVAL_CHAT_ID'),
        ('thread', 'ALFIE_APPROVAL_THREAD_ID'))}
    if not values['user'].isdigit() or int(values['user']) <= 0:
        raise ValueError('Set ALFIE_OWNER_TELEGRAM_USER_ID to the numeric bot owner Telegram ID in .env.local')
    if not values['chat'].lstrip('-').isdigit() or int(values['chat']) == 0:
        raise ValueError('Set ALFIE_APPROVAL_CHAT_ID to the owner review forum in .env.local')
    if not values['thread'].isdigit() or int(values['thread']) <= 0:
        raise ValueError('ALFIE_APPROVAL_THREAD_ID must be a positive numeric topic ID')
    return values


if __name__ == '__main__':
    if '--check' in sys.argv:
        policy()
        print('Private approval policy syntax valid.')
    else:
        print(json.dumps(policy()))
