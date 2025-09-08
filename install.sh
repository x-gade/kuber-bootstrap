#!/usr/bin/env bash
# install.sh — унифицированный инсталлятор Kuber Bootstrap
# Режимы:
#   -w   : python3 main.py worker
#   -cp  : python3 main.py control-plane
#   -cpb : python3 main.py control-plane --bootstrap (или 'bootstrap' позиционно как fallback)

set -Eeuo pipefail

# === Константы/пути ===
PROJECT_DIR="/opt/kuber-bootstrap"
MAIN_PY="${PROJECT_DIR}/main.py"
REQS_FILE="${PROJECT_DIR}/requirements.txt"
VENV_DIR="${PROJECT_DIR}/.venv"
DEBIAN_FRONTEND="${DEBIAN_FRONTEND:-noninteractive}"

# Пакеты APT
APT_PKGS=(python3-argcomplete python3-venv python3-pip)

# sudo если не root
if [[ "${EUID}" -ne 0 ]]; then
  SUDO="sudo"
else
  SUDO=""
fi

log() {
  local level="$1"; shift
  local msg="$*"
  case "${level}" in
    ok)   echo -e "[OK] ${msg}";;
    warn) echo -e "[WARN] ${msg}";;
    err)  echo -e "[ERROR] ${msg}" >&2;;
    *)    echo -e "[INFO] ${msg}";;
  esac
}

usage() {
  cat <<EOF
Usage: $0 MODE

MODE:
  -w    : запуск worker пайплайна              -> python main.py worker
  -cp   : запуск control-plane                 -> python main.py control-plane
  -cpb  : bootstrap control-plane (cp + boot)  -> python main.py control-plane --bootstrap
EOF
}

require_cmd() {
  local c="$1"
  command -v "$c" >/dev/null 2>&1 || { log err "Не найден бинарник: $c"; exit 127; }
}

apt_prepare() {
  require_cmd apt-get
  log info "apt-get update..."
  ${SUDO} apt-get update -y >/dev/null
  # Установка недостающих пакетов
  local to_install=()
  for p in "${APT_PKGS[@]}"; do
    if dpkg -s "$p" >/dev/null 2>&1; then
      log ok "Пакет уже установлен: $p"
    else
      to_install+=("$p")
    fi
  done
  if (( ${#to_install[@]} > 0 )); then
    log info "Устанавливаем пакеты: ${to_install[*]}"
    ${SUDO} apt-get install -y "${to_install[@]}" >/dev/null
    log ok "APT-пакеты установлены"
  fi
}

ensure_project_layout() {
  if [[ ! -f "${MAIN_PY}" ]]; then
    log err "Не найден ${MAIN_PY}. Проверь PROJECT_DIR=${PROJECT_DIR}"
    exit 1
  fi
  if [[ ! -f "${REQS_FILE}" ]]; then
    log warn "requirements.txt не найден: ${REQS_FILE} — пропущу установку Python-зависимостей"
  fi
}

create_or_update_venv() {
  require_cmd python3
  # Создать venv при отсутствии
  if [[ ! -d "${VENV_DIR}" ]]; then
    log info "Создаю виртуальное окружение: ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
    log ok "VENV создан"
  else
    log ok "VENV уже существует: ${VENV_DIR}"
  fi

  local PY="${VENV_DIR}/bin/python"
  local PIP="${VENV_DIR}/bin/pip"

  # Обновить pip/setuptools/wheel
  log info "Обновляю pip/setuptools/wheel внутри VENV..."
  "${PY}" -m pip install --upgrade pip setuptools wheel >/dev/null
  log ok "pip/setuptools/wheel обновлены"

  # Поставить зависимости из requirements.txt (с 3 ретраями)
  if [[ -f "${REQS_FILE}" ]]; then
    local tries=0 max_tries=3
    until "${PIP}" install -r "${REQS_FILE}"; do
      tries=$((tries+1))
      if (( tries >= max_tries )); then
        log err "Не удалось установить зависимости из ${REQS_FILE} после ${max_tries} попыток"
        exit 1
      fi
      log warn "Неудача установки зависимостей (попытка ${tries}/${max_tries}). Жду и повторю..."
      sleep 3
    done
    log ok "Python-зависимости установлены"
  fi

  # Гарантируем наличие argcomplete и в venv (main.py импортирует модуль)
  "${PIP}" install "argcomplete" >/dev/null || true
  log ok "Модуль argcomplete доступен в VENV"
}

run_worker() {
  local PY="${VENV_DIR}/bin/python"
  log info "Запуск worker пайплайна..."
  exec "${PY}" "${MAIN_PY}" worker
}

run_cp() {
  local PY="${VENV_DIR}/bin/python"
  log info "Запуск control-plane..."
  exec "${PY}" "${MAIN_PY}" control-plane
}

run_cpb() {
  local PY="${VENV_DIR}/bin/python"
  log info "Запуск control-plane bootstrap (--bootstrap)..."
  if "${PY}" "${MAIN_PY}" control-plane --bootstrap; then
    exit 0
  fi
  log warn "Флаг --bootstrap не сработал, пробую позиционный 'bootstrap'..."
  exec "${PY}" "${MAIN_PY}" control-plane bootstrap
}

main() {
  if [[ $# -ne 1 ]]; then usage; exit 2; fi
  local mode="$1"

  # 1) APT prereqs
  apt_prepare
  # 2) Проверка проекта
  ensure_project_layout
  # 3) Python venv + зависимости
  create_or_update_venv

  # 4) Запуск соответствующего режима
  case "${mode}" in
    -w)  run_worker ;;
    -cp) run_cp ;;
    -cpb) run_cpb ;;
    *) usage; exit 2 ;;
  esac
}

main "$@"
