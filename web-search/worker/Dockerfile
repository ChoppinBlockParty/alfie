# Alfie research/browser worker (../README.md).
# Self-built from debian:13; spec forbids unofficial Docker Hub images.
FROM debian:13

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Minimal Python base; Playwright brings its own driver and browser dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir \
        httpx==0.28.1 \
        websockets==15.0.1 \
        openai==2.6.1 \
        playwright==1.63.0

ENV PLAYWRIGHT_BROWSERS_PATH=/opt/browsers
RUN /opt/venv/bin/playwright install --with-deps chromium \
    && chmod -R a+rX /opt/browsers \
    && rm -rf /var/lib/apt/lists/*

# uid 10000, matching the rest of the stack. No home, no shell: this user exists to
# own a process, not to be logged into.
RUN groupadd -g 10000 worker \
    && useradd -u 10000 -g 10000 -M -d /nonexistent -s /usr/sbin/nologin worker

COPY browser.py codex.py retrieval.py research.py server.py /opt/websearch/

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/opt/websearch

USER 10000:10000
EXPOSE 8770

# No model credential is baked in or accepted in a job. Inference is brokered by
# the gateway over the existing authenticated connection.
ENTRYPOINT ["/opt/venv/bin/python3", "/opt/websearch/server.py"]
