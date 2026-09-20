"""Bounded research inference over the existing authenticated worker connection.

No listening endpoint, caller-selected URL/model/tools, or credential response. Provider
credentials stay in the gateway. The existing Hermes subscription transport is preserved;
this is not a new paid API fallback or a claim about public API support for that endpoint.
"""
import asyncio
import base64
import hashlib
import json
import time

MODEL = 'gpt-5.5'
BASE_URL = 'https://chatgpt.com/backend-api/codex'
PROMPTS = frozenset((
    'dce60bea582d3889d1185bb7cda5b854088ed5eea82fd290bfeac2dcf2fa2caf',
    '442e45c62dc39772b13c3aeec5f25ad19f23d8ad91d82c4a6edc7428ad3d1b35',
    '118583a73215f9e0d90743e23f1b229cd6bc9afa3f2deea5880e6d91c998b9ba',
))
MAX_INPUT = 256 * 1024
MAX_OUTPUT = 64 * 1024


def validate_request(message, job, expected):
    if not isinstance(message, dict) or set(message) != {'type', 'id', 'call', 'model', 'instructions', 'user'}:
        raise ValueError('Invalid inference frame')
    if message['type'] != 'inference' or message['id'] != job or type(message['call']) is not int \
            or message['call'] != expected or message['model'] != MODEL:
        raise ValueError('Inference binding mismatch')
    instructions, user = message['instructions'], message['user']
    if not isinstance(instructions, str) or not isinstance(user, str) \
            or len(user.encode()) > MAX_INPUT or len(instructions.encode()) > 4096 \
            or hashlib.sha256(instructions.encode()).hexdigest() not in PROMPTS:
        raise ValueError('Unreviewed or oversized inference request')


def parse_object(text):
    decoder = json.JSONDecoder()
    attempts = 0
    for index, character in enumerate(text):
        if character == '{':
            attempts += 1
            if attempts > 16:
                break
            try:
                value, _ = decoder.raw_decode(text[index:])
                if isinstance(value, dict):
                    return value
            except ValueError:
                pass
    raise ValueError('Model did not return an object')


class Broker:
    def __init__(self, token, job, depth):
        self.token, self.job = token, job
        self.limit = 3 if depth == 'quick' else 5
        self.calls, self.tokens = 0, 0
        self.deadline = time.monotonic() + 300

    async def infer(self, message):
        validate_request(message, self.job, self.calls + 1)
        remaining = self.deadline - time.monotonic()
        if self.calls >= self.limit or self.tokens >= 120000 or remaining <= 0:
            raise ValueError('Research inference budget exhausted')
        self.calls += 1
        from openai import AsyncOpenAI
        headers = {'User-Agent': 'HermesAgent/0.1.0', 'originator': 'hermes-agent'}
        try:
            part = self.token.split('.')[1]
            claims = json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))
            account = claims.get('https://api.openai.com/auth', {}).get('chatgpt_account_id')
            if isinstance(account, str) and account:
                headers['ChatGPT-Account-ID'] = account
        except (ValueError, IndexError, TypeError):
            pass
        client = AsyncOpenAI(api_key=self.token, base_url=BASE_URL, default_headers=headers, max_retries=0)
        stream = None
        chunks, size, tokens, complete = [], 0, 0, False
        try:
            async with asyncio.timeout(min(120, remaining)):
                stream = await client.responses.create(model=MODEL, instructions=message['instructions'],
                    input=[{'role': 'user', 'content': message['user']}], store=False, stream=True,
                    timeout=min(120, remaining))
                async for event in stream:
                    kind = getattr(event, 'type', '')
                    if kind == 'response.output_text.delta':
                        value = getattr(event, 'delta', '') or ''
                        size += len(value.encode())
                        if size > MAX_OUTPUT:
                            raise ValueError('Inference output limit exceeded')
                        chunks.append(value)
                    elif kind in ('response.failed', 'error', 'response.incomplete'):
                        raise ValueError('Inference failed')
                    elif kind == 'response.completed':
                        usage = getattr(getattr(event, 'response', None), 'usage', None)
                        tokens = int(getattr(usage, 'total_tokens', 0) or 0)
                        complete = True
                if not complete:
                    raise ValueError('Incomplete inference stream')
        finally:
            if stream is not None:
                await stream.close()
            await client.close()
        self.tokens += max(0, tokens)
        return {'type': 'inference_result', 'id': self.job, 'call': self.calls,
                'data': parse_object(''.join(chunks)), 'tokens': tokens}
