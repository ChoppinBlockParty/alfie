# Telegram media preprocessing

This subsystem owns the availability and preprocessing of authenticated Telegram voice notes and
photographs before task classification. Voice is decoded and transcribed locally with pinned
`faster-whisper==1.2.1` using the `base` model. Images use the configured model-vision path.
Telegram voice clips use no additional VAD pass: real two-second speech was incorrectly discarded
by VAD plus the upstream `0.6/-1.0` confidence defaults. The subsystem owns narrower tested
confidence settings (`no_speech=0.75`, `logprob=-1.3`) while retaining the segment filter.

Media processing does not itself grant authority. A successful transcript from a direct,
authenticated owner voice note is treated like the owner's typed request and may select a normal
task mode, but it cannot approve an exact account effect. Pixels/OCR remain untrusted image data
and force tool-free chat. Unsupported attachments fail before an agent task starts.

STT remains Hermes's native inbound implementation; this subsystem configures and invokes it
before effect selection so spoken requests can receive the same tools as typed requests. An empty
transcript is not rejected by permissions: the message continues through Hermes's normal
tool-free untranscribed-audio response path.

`deploy.sh` installs the allowlisted STT packages into the durable gateway dependency target,
mounts `alfie_media.py` read-only, applies the owned short-voice configuration and recreates only
the gateway after a rollback backup. This WIP subsystem deliberately has no synthetic media test
harness; actual owner Telegram voice/photo requests provide the useful integration feedback.

The subsystem currently shares the credentialed gateway process because Telegram media download,
the configured model client and existing resource limits are there. This is a logical ownership
boundary, not process isolation. Moving decode/vision to a dedicated low-privilege worker remains a
future hardening option; it is not required for the two use cases to function.
