"""Strict bounded data validation before any Google proposal or execution."""
from email.utils import getaddresses
import json
import math
import re


def addresses(value, *, bare=False):
    if not isinstance(value, str) or len(value) > 2000 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Invalid recipient list')
    parsed = getaddresses([value])
    if not 1 <= len(parsed) <= 20 or any(not re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}", addr)
            for _, addr in parsed) or bare and any(name for name, _ in parsed):
        raise ValueError('Use valid explicit email addresses (at most 20)')
    return [addr for _, addr in parsed]


def cells(value):
    try:
        data = json.loads(value)
    except RecursionError:
        raise ValueError('Nested values exceed the schema') from None
    if not isinstance(data, list) or not 1 <= len(data) <= 50 or any(
            not isinstance(row, list) or not 1 <= len(row) <= 20 for row in data) \
            or sum(map(len, data)) > 200:
        raise ValueError('Values must be 1–50 rows, 1–20 columns and at most 200 cells')
    for row in data:
        for cell in row:
            if type(cell) not in (str, bool, int, float) or isinstance(cell, str) and (len(cell) > 2000 or '\x00' in cell) \
                    or type(cell) in (int, float) and (abs(cell) > 1e15 or not math.isfinite(cell)):
                raise ValueError('Cells must be bounded strings, booleans or finite numbers')
    return data


def bounded_range(value):
    match = re.fullmatch(r"(?:(?:'[^'\r\n]{1,100}'|[A-Za-z0-9_ ]{1,100})!)?([A-Z]{1,3})([1-9][0-9]{0,6})(?::([A-Z]{1,3})([1-9][0-9]{0,6}))?", value)
    if not match:
        raise ValueError('Use an explicit bounded A1 cell range, not whole columns or named ranges')
    col1, row1, col2, row2 = match.groups()
    def col(v):
        n = 0
        for c in v:
            n = n * 26 + ord(c) - 64
        return n
    rows, cols = int(row2 or row1) - int(row1) + 1, col(col2 or col1) - col(col1) + 1
    if not 1 <= rows <= 50 or not 1 <= cols <= 20 or rows * cols > 200:
        raise ValueError('Range exceeds the 200-cell read/review budget')
    return rows, cols


def validate(operation, arguments):
    for field in ('to', 'cc', 'attendees'):
        if field in arguments:
            addresses(arguments[field], bare=field == 'attendees')
    if operation.startswith('sheets.'):
        if 'range' in arguments:
            bounded_range(arguments['range'])
        if 'values' in arguments:
            data = cells(arguments['values'])
            rows, cols = bounded_range(arguments['range'])
            if any(len(row) > cols for row in data) or operation == 'sheets.update' and len(data) > rows:
                raise ValueError('Values extend outside the reviewed range dimensions')
