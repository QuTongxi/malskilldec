# Local development shell
export PATH="/usr/local/bin:$PATH"
if [ -f "$HOME/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$HOME/.env"
  set +a
fi
