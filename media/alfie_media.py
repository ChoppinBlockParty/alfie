"""Authenticated Telegram media preprocessing before task classification.

This module owns media availability and provenance. It never grants tools or effects; the task
policy consumes only its text result and an image-provenance flag.
"""

STT_LOCAL_CONFIG = {
    'model': 'base',
    'language': 'en',
    # Telegram clips are already bounded. VAD plus the upstream defaults discarded real
    # two-second speech as silence; confidence filtering remains active below.
    'vad': False,
    'no_speech_prob_threshold': 0.75,
    'logprob_threshold': -1.3,
}


class MediaError(ValueError):
    pass


def configure_stt(config):
    if not isinstance(config, dict):
        raise ValueError('Gateway config must be a mapping')
    stt = config.setdefault('stt', {})
    if not isinstance(stt, dict):
        raise ValueError('Gateway stt config must be a mapping')
    stt['enabled'] = True
    local = stt.setdefault('local', {})
    if not isinstance(local, dict):
        raise ValueError('Gateway stt.local config must be a mapping')
    local.update(STT_LOCAL_CONFIG)
    return config


async def prepare_owner_media(gateway, event, text):
    """Return ``(owner_text, image_task)`` for a bounded Telegram media event."""
    media_urls = list(getattr(event, 'media_urls', None) or [])
    media_types = list(getattr(event, 'media_types', None) or [])
    if not media_urls:
        return text, False

    audio_paths = gateway._pending_event_audio_paths(event)
    image_only = len(media_types) == len(media_urls) and all(
        isinstance(kind, str) and kind.startswith('image/') for kind in media_types)
    if audio_paths and len(audio_paths) == len(media_urls):
        # Use Hermes's native transcription implementation. The permission layer needs the
        # transcript only to choose tools; it must not turn an STT miss into a rejected message.
        transcript = await gateway._prepare_clarify_reply_text(event)
        if transcript:
            return transcript, False
        # Hermes has cached its normal untranscribed-audio note on the event. Let the native
        # inbound pipeline present that to a tool-free agent, as it did before task permissions.
        return 'Help the owner with the attached voice message.', True
    if image_only:
        # Pixels and OCR are data, never authority. The policy forces this task to tool-free chat.
        return text.strip() or 'Describe and help with the attached photograph.', True
    raise MediaError('This attachment type is not supported. Send text, a Telegram voice note, or photographs.')
