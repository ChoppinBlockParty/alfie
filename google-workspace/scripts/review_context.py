"""Fixed target-only readbacks for write reviews. Not a registered model operation."""
import json
import sys
from google_api import build_service


def context(operation, args):
    if operation == 'gmail.send':
        return {'effect': 'Send this exact message to all to/cc recipients; no automatic retry.'}
    if operation == 'gmail.modify':
        api = build_service('gmail', 'v1')
        msg = api.users().messages().get(userId='me', id=args['message_id'], format='metadata',
            metadataHeaders=['From', 'To', 'Subject']).execute()
        labels = api.users().labels().list(userId='me').execute().get('labels', [])
        names = {x['id']: x['name'] for x in labels}
        requested = {key: [value for value in args.get(key, '').split(',') if value]
                     for key in ('add_labels', 'remove_labels')}
        if any(label not in names for group in requested.values() for label in group):
            raise ValueError('Unknown label')
        return {'message_id': msg['id'], 'headers': msg.get('payload', {}).get('headers', []),
                'current_labels': sorted(msg.get('labelIds', [])),
                'label_names': {key: {label: names[label] for label in group} for key, group in requested.items()}}
    if operation.startswith('calendar.'):
        api = build_service('calendar', 'v3')
        calendar = api.calendars().get(calendarId=args.get('calendar', 'primary'),
                                       fields='id,summary,timeZone').execute()
        if operation == 'calendar.create':
            return {'calendar': calendar, 'effect': 'Create event; attendee addresses are disclosure destinations.'}
        if operation == 'calendar.delete':
            event = api.events().get(calendarId=args.get('calendar', 'primary'), eventId=args['event_id'],
                fields='id,etag,summary,start,end,attendees(email),status').execute()
            return {'calendar': calendar, 'delete_event': event}
    if operation in ('docs.create', 'sheets.create'):
        return {'effect': 'Create a new document/spreadsheet with the exact supplied content.'}
    if operation == 'drive.create-folder' and args.get('parent', 'root') == 'root':
        return {'parent': 'My Drive root (implicit account root)', 'effect': 'Create a new folder, not a duplicate check.'}
    field = {'drive.create-folder': 'parent', 'docs.append': 'doc_id',
             'sheets.update': 'sheet_id', 'sheets.append': 'sheet_id'}.get(operation)
    if field is None:
        raise ValueError('Unsupported review context')
    file = build_service('drive', 'v3').files().get(fileId=args[field],
        fields='id,name,mimeType,parents,shared,version,trashed').execute()
    if file.get('trashed'):
        raise ValueError('Target is trashed')
    expected = {'drive.create-folder': 'application/vnd.google-apps.folder',
                'docs.append': 'application/vnd.google-apps.document',
                'sheets.update': 'application/vnd.google-apps.spreadsheet',
                'sheets.append': 'application/vnd.google-apps.spreadsheet'}[operation]
    if file.get('mimeType') != expected:
        raise ValueError('Wrong target type')
    result = {'target': file, 'disclosure': 'Existing viewers/inherited permissions may expose the new content.'}
    if operation == 'sheets.update':
        old = build_service('sheets', 'v4').spreadsheets().values().get(
            spreadsheetId=args['sheet_id'], range=args['range'], valueRenderOption='FORMULA').execute()
        result['previous_values'] = old.get('values', [])
        result['effect'] = 'Replace supplied cells with literal RAW values; strings are not formulas.'
    elif operation == 'sheets.append':
        result['effect'] = 'Append literal RAW values; Google finds the table end within the range and inserts rows.'
    elif operation == 'docs.append':
        result['effect'] = 'Append the exact text to the end of this document.'
    else:
        result['effect'] = 'Create a new child folder under this exact parent.'
    return result


if __name__ == '__main__':
    try:
        result = context(sys.argv[1], json.loads(sys.argv[2]))
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, allow_nan=False))
    except Exception:
        print('Target readback failed', file=sys.stderr)
        sys.exit(1)
