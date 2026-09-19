# Alfie sandbox — the container the gateway reaches over SSH (main-spec.md D9).
#
# Built from debian:13, the same base as upstream's own image (Dockerfile:52).
# No unofficial Docker Hub namespace, which also rules out upstream's default
# sandbox image nikolaik/python-nodejs.
FROM debian:13

ENV DEBIAN_FRONTEND=noninteractive

# No Node. Nothing Alfie runs needs it; add it when a skill does.
RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-server ca-certificates python3 python3-venv python3-pip \
        ripgrep git curl \
    && rm -rf /var/lib/apt/lists/*

# uid/gid 10000 matches the gateway. That is what makes every bind mount readable
# without an ACL, and it is why the rootless plan's uid-mapping risk does not arise.
# -p '*' is load-bearing: useradd leaves the password field '!', which means
# "locked", and with UsePAM no sshd refuses a locked account outright — it logs
# "User agent not allowed because account is locked" and answers the client with
# a bare "Permission denied (publickey)", which looks like a key problem and is not.
# '*' means "no password can ever match", which is what we want, without the lock.
RUN groupadd -g 10000 agent \
    && useradd -u 10000 -g 10000 -m -d /home/agent -s /bin/bash -p '*' agent \
    && mkdir -p /home/agent/.ssh /home/agent/.hermes \
    && chown -R 10000:10000 /home/agent \
    && chmod 700 /home/agent/.ssh

# Google operations run only in the gateway plugin. No Google SDK or credentials here.
RUN ln -s /usr/bin/python3 /usr/local/bin/python

COPY sshd-alfie.conf /etc/ssh/sshd_config.d/10-alfie.conf
COPY entrypoint.sh /usr/local/sbin/entrypoint.sh
RUN chmod 644 /etc/ssh/sshd_config.d/10-alfie.conf \
    && chmod 755 /usr/local/sbin/entrypoint.sh

# 2222, not 22: a high port needs no CAP_NET_BIND_SERVICE. The gateway is pointed
# at it with TERMINAL_SSH_PORT, which the backend honours (gateway/run.py:1831,
# tools/environments/ssh.py:107).
EXPOSE 2222
ENTRYPOINT ["/usr/local/sbin/entrypoint.sh"]
