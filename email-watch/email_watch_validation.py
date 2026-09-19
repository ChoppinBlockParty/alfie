"""Validate model output as data. Successful validation never authorizes an action."""
from datetime import date, datetime
import math
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def fields(value, names):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError('Invalid extraction fields')


def text(value, limit=1000):
    if not isinstance(value, str) or len(value) > limit or '\x00' in value:
        raise ValueError('Invalid extraction text')


def day(value, *, nullable=True, timestamp=False, offset=False):
    if value is None and nullable:
        return
    text(value, 40)
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            date.fromisoformat(value)
        elif timestamp and 'T' in value:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if offset and parsed.utcoffset() is None:
                raise ValueError('Missing timezone offset')
        else:
            raise ValueError('Invalid date')
    except (ValueError, OverflowError):
        raise ValueError('Invalid extraction date') from None


def zone(value):
    text(value, 100)
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError):
        raise ValueError('Invalid extraction timezone') from None


def items(value, maximum=10):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError('Invalid extraction list')
    return value


def validate_results(data, input_ids):
    fields(data, 'emails')
    expected = set(input_ids)
    result = {}
    for entry in items(data['emails'], 10):
        fields(entry, 'id important suspicious summary action deadline todos events travel bill')
        mid = entry['id']
        text(mid, 200)
        if mid not in expected or mid in result:
            raise ValueError('Unexpected or duplicate message ID')
        if type(entry['important']) is not bool or type(entry['suspicious']) is not bool:
            raise ValueError('Extraction flags must be booleans')
        for name in ('summary', 'action'):
            text(entry[name])
        day(entry['deadline'], timestamp=True)
        for todo in items(entry['todos']):
            fields(todo, 'text due')
            text(todo['text'])
            day(todo['due'])
        for event in items(entry['events'], 5):
            fields(event, 'title start end tz location confirmed')
            for name in ('title', 'location'):
                text(event[name])
            if type(event['confirmed']) is not bool:
                raise ValueError('confirmed must be boolean')
            zone(event['tz'])
            day(event['start'], nullable=False, timestamp=True, offset=True)
            day(event['end'], timestamp=True, offset=True)
        for trip in items(entry['travel'], 5):
            fields(trip, 'destination tz start end')
            text(trip['destination'], 200)
            zone(trip['tz'])
            day(trip['start'], nullable=False)
            day(trip['end'])
            if trip['end'] is not None and trip['end'] < trip['start']:
                raise ValueError('Invalid trip interval')
        bill = entry['bill']
        if bill is not None:
            fields(bill, 'counterparty amount currency due')
            text(bill['counterparty'])
            amount = bill['amount']
            if type(amount) not in (int, float) or not 0 <= amount <= 1e12 or not math.isfinite(amount):
                raise ValueError('Invalid bill amount')
            if not isinstance(bill['currency'], str) or not re.fullmatch('[A-Z]{3}', bill['currency']):
                raise ValueError('Invalid currency')
            day(bill['due'])
        result[mid] = entry
    if set(result) != expected:
        raise ValueError('Missing message extraction')
    return result
