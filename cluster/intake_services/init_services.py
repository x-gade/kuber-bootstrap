#!/usr/bin/env python3
"""
Node Intake Services Launcher
Лаунчер сервисов Node Intake

This script acts as a unified entry point to launch specific node intake services.
Depending on the mode it either installs and starts a systemd service (for control-plane)
or runs a one-shot worker bootstrap/delete.

Этот скрипт является единой точкой входа для запуска intake-сервисов.
В зависимости от режима он либо устанавливает и запускает systemd-сервис (для control-plane),
либо выполняет одноразовый запуск bootstrap/delete для worker-ноды.
"""

import argparse
import subprocess
import sys
from pathlib import Path

# === Добавляем корень проекта для логгера ===
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from utils.logger import log  # централизованный логгер

# === Пути ===
CURRENT_DIR = Path(__file__).resolve().parent
CPS_SERVICE_SCRIPT = CURRENT_DIR / "cps_service.py"
WORKER_BOOTSTRAP = CURRENT_DIR / "worker_bootstrap.py"
WORKER_DELETE = CURRENT_DIR / "worker_delete.py"
SYSTEMD_TEMPLATE = PROJECT_ROOT / "data/systemd/intake_ipam.service.j2"
SYSTEMD_TARGET = Path("/etc/systemd/system/intake_ipam.service")


def install_and_start_systemd_service():
    """
    Install and start the intake_ipam systemd service
    Устанавливает и запускает systemd-сервис intake_ipam
    """
    if not SYSTEMD_TEMPLATE.exists():
        log(f"Шаблон systemd не найден: {SYSTEMD_TEMPLATE}", "error")
        sys.exit(1)

    log("Копирование systemd юнита intake_ipam...", "info")
    # Просто копируем шаблон как есть (пока без jinja-рендера)
    SYSTEMD_TARGET.write_text(SYSTEMD_TEMPLATE.read_text())

    log("Перезапуск systemd-демона...", "info")
    subprocess.run(["systemctl", "daemon-reexec"], check=True)

    log("Включение и запуск intake_ipam...", "info")
    subprocess.run(["systemctl", "enable", "--now", "intake_ipam.service"], check=True)

    log("Сервис intake_ipam успешно установлен и запущен", "ok")
    subprocess.run(["systemctl", "status", "--no-pager", "intake_ipam.service"])


def run_service(script_path: Path, extra_args=None):
    """
    Run a given Python service as a subprocess and stream its output.
    Запускает указанный Python-сервис как subprocess и выводит его результат.

    Arguments / Аргументы:
        script_path (Path) - full path to the target Python script / полный путь к целевому Python-скрипту
        extra_args (list) - additional CLI arguments passed to the script / дополнительные аргументы для скрипта
    """
    if not script_path.exists():
        log(f"Сервис не найден: {script_path}", "error")
        sys.exit(1)

    cmd = [sys.executable, str(script_path)]
    if extra_args:
        cmd.extend(extra_args)

    log(f"Запуск сервиса: {' '.join(cmd)}", "info")

    try:
        subprocess.run(cmd, check=True)
        log(f"Сервис {script_path.name} завершён успешно", "ok")
    except subprocess.CalledProcessError as e:
        log(f"Сервис {script_path.name} завершился с ошибкой: {e}", "error")
        sys.exit(e.returncode)


def main():
    """
    Main entry point for the service launcher.
    Точка входа для лаунчера сервисов.

    It parses the CLI arguments, determines the mode and:
     - for control-plane installs and starts systemd unit (intake_ipam)
     - for worker runs one-shot bootstrap/delete scripts

    Парсит CLI аргументы, определяет режим и:
     - для control-plane устанавливает и запускает systemd-юнит intake_ipam
     - для worker выполняет одноразовый bootstrap/delete
    """
    parser = argparse.ArgumentParser(
        description="Node Intake Services Launcher"
    )

    parser.add_argument(
        "-cps",
        action="store_true",
        help="Install & start control-plane intake_ipam systemd service"
    )

    parser.add_argument(
        "-wb",
        action="store_true",
        help="Run worker bootstrap mode / Запустить bootstrap worker-ноды"
    )

    parser.add_argument(
        "-wd",
        action="store_true",
        help="Run worker delete mode / Запустить удаление worker-ноды"
    )

    args = parser.parse_args()

    if args.cps:
        log("Режим: Control-plane systemd service install (-cps)", "ok")
        install_and_start_systemd_service()

    elif args.wb:
        log("Режим: Worker bootstrap (-wb)", "ok")
        run_service(WORKER_BOOTSTRAP)

    elif args.wd:
        log("Режим: Worker delete (-wd)", "warn")
        run_service(WORKER_DELETE)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
