# Sourced by Bash deploy scripts. .env.local is trusted operator-owned shell syntax.
# Load once so nested deployment scripts inherit the same configuration.
if [[ ${ALFIE_LOCAL_ENV_LOADED:-} != 1 ]]; then
    ALFIE_REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
    if [[ -f "$ALFIE_REPO_ROOT/.env.local" ]]; then
        set -a
        source "$ALFIE_REPO_ROOT/.env.local"
        set +a
    fi
    export ALFIE_LOCAL_ENV_LOADED=1
fi
: "${HOST:?Set HOST in the ignored repository .env.local}"
export HOST
