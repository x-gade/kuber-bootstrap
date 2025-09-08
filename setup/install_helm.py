#!/usr/bin/env python3
"""
Install Helm package manager for Kubernetes.
Устанавливает Helm — менеджер пакетов для Kubernetes.
"""

import os
import sys
import subprocess
import shutil

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
sys.path.append(PROJECT_ROOT)

from utils.logger import log


def run(cmd: list, cwd=None):
    """
    Run a shell command and return success status.
    Выполняет shell-команду и возвращает статус успешности.

    :param cmd: Команда в виде списка аргументов
    :param cwd: Каталог, в котором выполняется команда (опционально)
    :return: True если команда выполнена успешно, иначе False
    """
    try:
        subprocess.run(cmd, check=True, cwd=cwd)
        return True
    except subprocess.CalledProcessError:
        return False


def install_helm():
    """
    Install Helm via official APT repository if not already installed.
    Устанавливает Helm через официальный репозиторий APT, если он ещё не установлен.
    """
    if shutil.which("helm"):
        log("Helm уже установлен. Пропускаем.", "ok")
        return

    log("Установка Helm из официального репозитория...", "info")

    cmds = [
        ["curl", "-fsSL", "https://baltocdn.com/helm/signing.asc", "-o", "/usr/share/keyrings/helm.gpg"],
        ["gpg", "--dearmor", "--yes", "-o", "/usr/share/keyrings/helm.gpg", "/usr/share/keyrings/helm.gpg"],
        ["bash", "-c", 'echo "deb [signed-by=/usr/share/keyrings/helm.gpg] https://baltocdn.com/helm/stable/debian/ all main" > /etc/apt/sources.list.d/helm-stable.list'],
        ["apt", "update"],
        ["apt", "install", "-y", "helm"]
    ]

    for cmd in cmds:
        if not run(cmd):
            log(f"Ошибка при выполнении: {' '.join(cmd)}", "error")
            sys.exit(1)

    if shutil.which("helm"):
        log("Helm успешно установлен.", "ok")
    else:
        log("Helm не обнаружен после установки. Проверь вручную.", "error")
        sys.exit(1)


if __name__ == "__main__":
    """
    Entrypoint: install Helm if missing.
    Точка входа: установить Helm при отсутствии.
    """
    log("Установка Helm...", "start")
    install_helm()
