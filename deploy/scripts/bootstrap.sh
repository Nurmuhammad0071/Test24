#!/usr/bin/env bash
set -euo pipefail

APP_USER="test24"
APP_GROUP="test24"
APP_ROOT="/opt/test24"
APP_DIR="${APP_ROOT}/app"
VENV_DIR="${APP_ROOT}/venv"
ENV_DIR="/etc/test24"
ENV_FILE="${ENV_DIR}/test24.env"
SERVICE_NAME="test24"
REPO_URL_DEFAULT="https://github.com/Nurmuhammad0071/Test24.git"
REPO_URL="${REPO_URL_DEFAULT}"
BRANCH="main"
DOMAIN="api.test24.uz"
REPO_TOKEN=""

usage() {
  cat <<'EOF'
Usage: bootstrap.sh [--branch main] [--domain api.test24.uz] [--repo-token <token>]

Bootstraps a fresh Ubuntu/Debian server for the Test24 backend.
Must be executed as root. Re-runnable (safe to run multiple times).
EOF
  exit 1
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "[ERR] Run this script as root." >&2
    exit 2
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --branch)
        BRANCH="$2"; shift 2;;
      --domain)
        DOMAIN="$2"; shift 2;;
      --repo-token)
        REPO_TOKEN="$2"; shift 2;;
      --repo-url)
        REPO_URL="$2"; shift 2;;
      -h|--help)
        usage;;
      *)
        echo "Unknown flag: $1"; usage;;
    esac
  done
}

apt_packages() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y git python3 python3-venv python3-pip nginx postgresql-client curl
}

ensure_user() {
  if ! id -u "${APP_USER}" >/dev/null 2>&1; then
    useradd --system --home "${APP_ROOT}" --shell /usr/sbin/nologin "${APP_USER}"
  fi
  if ! getent group "${APP_GROUP}" >/dev/null 2>&1; then
    groupadd --system "${APP_GROUP}"
    usermod -g "${APP_GROUP}" "${APP_USER}"
  fi
}

prepare_dirs() {
  mkdir -p "${APP_DIR}" "${VENV_DIR}" "${ENV_DIR}" "${APP_ROOT}/logs" /run/${SERVICE_NAME}
  chown -R "${APP_USER}:${APP_GROUP}" "${APP_ROOT}" /run/${SERVICE_NAME}
  chmod 750 "${APP_ROOT}"
}

clone_repo() {
  local auth_repo="${REPO_URL}"
  if [[ -n "${REPO_TOKEN}" ]]; then
    auth_repo="https://${REPO_TOKEN}@${REPO_URL#https://}"
  fi

  if [[ ! -d "${APP_DIR}/.git" ]]; then
    sudo -u "${APP_USER}" git clone --branch "${BRANCH}" --single-branch "${auth_repo}" "${APP_DIR}"
  else
    pushd "${APP_DIR}" >/dev/null
    sudo -u "${APP_USER}" git fetch origin
    sudo -u "${APP_USER}" git checkout "${BRANCH}"
    sudo -u "${APP_USER}" git reset --hard "origin/${BRANCH}"
    popd >/dev/null
  fi
}

setup_env_file() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    cp "${APP_DIR}/example.env" "${ENV_FILE}"
    chown root:"${APP_GROUP}" "${ENV_FILE}"
    chmod 640 "${ENV_FILE}"
    echo "[INFO] Remember to edit ${ENV_FILE} with production secrets."
  fi
}

setup_venv() {
  if [[ ! -f "${VENV_DIR}/bin/activate" ]]; then
    python3 -m venv "${VENV_DIR}"
    chown -R "${APP_USER}:${APP_GROUP}" "${VENV_DIR}"
  fi
}

install_systemd() {
  cp "${APP_DIR}/deploy/systemd/test24.service" "/etc/systemd/system/${SERVICE_NAME}.service"
  systemctl daemon-reload
  systemctl enable "${SERVICE_NAME}.service"
}

install_nginx() {
  cp "${APP_DIR}/deploy/nginx/test24.conf" /etc/nginx/sites-available/test24.conf
  sed -i "s/server_name _.*/server_name ${DOMAIN};/" /etc/nginx/sites-available/test24.conf
  ln -sf /etc/nginx/sites-available/test24.conf /etc/nginx/sites-enabled/test24.conf
  nginx -t
  systemctl reload nginx
}

run_update() {
  "${APP_DIR}/deploy/scripts/update.sh" --branch "${BRANCH}" --domain "${DOMAIN}" --skip-pull-if-clean
}

main() {
  parse_args "$@"
  require_root
  apt_packages
  ensure_user
  prepare_dirs
  clone_repo
  setup_env_file
  setup_venv
  install_systemd
  install_nginx
  run_update
  echo "[DONE] Bootstrap complete. Service status:"
  systemctl status "${SERVICE_NAME}" --no-pager
}

main "$@"


