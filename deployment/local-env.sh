# Sourced by Bash deploy scripts. .env.local is trusted operator-owned shell syntax.
# zsh has its own HOST parameter and no BASH_SOURCE: reject it before using either.
if [ -z "${BASH_VERSION:-}" ] || [ -n "${ZSH_VERSION:-}" ]; then
    printf '%s\n' 'local-env.sh requires Bash. Run /bin/bash and source it there; do not use the current shell HOST as the deployment target.' >&2
    return 1 2>/dev/null || exit 1
fi
# Load once so nested deployment scripts inherit the same configuration.
if [[ ${ALFIE_LOCAL_ENV_LOADED:-} != 1 ]]; then
    ALFIE_REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
    if [[ -f "$ALFIE_REPO_ROOT/.env.local" ]]; then
        set -a
        source "$ALFIE_REPO_ROOT/.env.local" || { set +a; return 1; }
        set +a
    fi
    export ALFIE_LOCAL_ENV_LOADED=1
fi
: "${ALFIE_VPS_HOST:?Set ALFIE_VPS_HOST in the ignored repository .env.local}"
export ALFIE_VPS_HOST
