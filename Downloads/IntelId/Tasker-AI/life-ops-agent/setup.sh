#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
FRONTEND_DIR="${ROOT_DIR}/frontend"

if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${ROOT_DIR}/requirements.txt"

if [[ ! -f "${ROOT_DIR}/.env" && -f "${ROOT_DIR}/.env.example" ]]; then
  cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
  echo "Created .env from .env.example. Please add your API keys."
fi

if [[ -d "${FRONTEND_DIR}" && ! -f "${FRONTEND_DIR}/.env" && -f "${FRONTEND_DIR}/.env.example" ]]; then
  cp "${FRONTEND_DIR}/.env.example" "${FRONTEND_DIR}/.env"
  echo "Created frontend/.env from frontend/.env.example."
fi
