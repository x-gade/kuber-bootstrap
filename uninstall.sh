#!/usr/bin/env bash
# uninstall.sh — унифицированный деинсталлятор Kuber Bootstrap
# Режимы:
#   -wd  : worker delete       -> python init_services.py -wd ; utils/cleanup_kuber.sh
#   -cpd : control-plane del   -> python init_services.py -cpd; utils/cleanup_kuber.sh
#
# Поведение:
#   1) Пытается использовать venv (.venv/bin/python), если есть; иначе — системный python3.
#   2) Сначала делает кластерное удаление через init_services.py (опрос актуального токена и права).
#   3) Затем выполняет локовую очистку (cleanup_kuber.sh), даже если шаг 2 завершился ошибкой (логи предупредят).
#   4) Коды выхода: 0 — успех; 10/11 — ошибки init_services; 20 — ошибка cleanup.

set -Eeuo pipefail

PROJECT_DIR="/opt/kuber-bootstrap"
VENV_PY="${PROJECT_DIR}/.venv/bin/python"
SYS_PY="python3"

INIT_SERV="${PROJECT_DIR}/cluster/intake_services/init_services.py"
CLEAN_SH="${PROJECT_DIR}/utils/cleanup_kuber.sh"

# sudo при необходимости (для локальной очистки)
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
  -wd   : удалить worker-ноду (init_services.py -wd) и выполнить локовую очистку
  -cpd  : удалить control-plane узел (init_services.py -cpd) и выполнить локовую очистку

Переменные окружения:
  PYTHON_BIN=/path/to/python    — принудительно указать интерпретатор Python
  FORCE_CLEANUP=1               — выполнять cleanup даже если init_services завершился ошибкой (по умолчанию выполняется всегда)
EOF
}

require_file() {
  local f="$1"
  [[ -f "$f" ]] || { log err "Файл не найден: $f"; exit 1; }
}

choose_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    echo "${PYTHON_BIN}"
    return
  fi
  if [[ -x "${VENV_PY}" ]]; then
    echo "${VENV_PY}"
  else
    if command -v "${SYS_PY}" >/dev/null 2>&1; then
      echo "${SYS_PY}"
    else
      log err "Не найден python3 и отсутствует venv: ${VENV_PY}"
      exit 127
    fi
  fi
}

run_init_services() {
  local mode_flag="$1"  # -wd | -cpd
  local PYBIN="$2"

  log info "Запуск init_services.py ${mode_flag} (опрос токена/удаление узла в кластере)..."
  set +e
  "${PYBIN}" "${INIT_SERV}" "${mode_flag}"
  local rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    log ok "init_services.py ${mode_flag} завершён успешно"
  else
    log warn "init_services.py ${mode_flag} завершился с кодом ${rc}"
  fi
  return $rc
}

run_cleanup() {
  require_file "${CLEAN_SH}"
  # гарантируем исполняемость
  if [[ ! -x "${CLEAN_SH}" ]]; then
    ${SUDO} chmod +x "${CLEAN_SH}" || true
  fi
  log info "Выполняю локовую очистку (cleanup_kuber.sh)..."
  set +e
  ${SUDO} "${CLEAN_SH}"
  local rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    log ok "Локовая очистка завершена успешно"
  else
    log err "Ошибка локовой очистки (cleanup_kuber.sh), код ${rc}"
  fi
  return $rc
}

main() {
  if [[ $# -ne 1 ]]; then usage; exit 2; fi
  local mode="$1"

  require_file "${INIT_SERV}"
  require_file "${PROJECT_DIR}/main.py"  # базовая проверка структуры проекта

  local PYBIN
  PYBIN="$(choose_python)"
  log info "Использую Python интерпретатор: ${PYBIN}"

  local init_rc=0
  case "${mode}" in
    -wd)  run_init_services "-wd"  "${PYBIN}" || init_rc=$? ;;
    -cpd) run_init_services "-cpd" "${PYBIN}" || init_rc=$? ;;
    *)    usage; exit 2 ;;
  esac

  # Выполняем cleanup всегда, чтобы гарантированно подчистить локалку.
  local clean_rc=0
  run_cleanup || clean_rc=$?

  # Итоговые коды: приоритетнее ошибки init_services (кластер), но покажем обе
  if [[ $init_rc -ne 0 || $clean_rc -ne 0 ]]; then
    if [[ $init_rc -ne 0 ]]; then
      # 10/11 — наглядные коды под разные режимы
      [[ "${mode}" == "-wd"  ]] && exit 10 || true
      [[ "${mode}" == "-cpd" ]] && exit 11 || true
      # fallback
      exit 10
    fi
    # init ок, но cleanup упал
    exit 20
  fi

  log ok "Деинсталляция завершена."
}

main "$@"
