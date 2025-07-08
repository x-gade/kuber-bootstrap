# setup/install_dependencies.py

"""
Installs essential system dependencies for Kubernetes node initialization.
Устанавливает системные зависимости для инициализации узла Kubernetes.
"""

import os
import sys
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log

REQUIRED_PACKAGES = [
    "apt-transport-https",
    "ca-certificates",
    "curl",
    "gnupg",
    "lsb-release",
    "containerd",
    "conntrack",
    "iproute2",
    "socat"
]

def run(cmd: str):
    """
    Executes a shell command and exits on failure.
    Выполняет команду оболочки и завершает работу при ошибке.
    """
    log(f"Выполняю: {cmd}", "info")
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        log(f"Ошибка при выполнении: {e}", "error")
        sys.exit(1)

def install_dependencies():
    """
    Installs required system packages via apt.
    Устанавливает нужные системные пакеты через apt.
    """
    log("Обновление списка пакетов...", "info")
    run("apt-get update")

    joined = " ".join(REQUIRED_PACKAGES)
    log("Установка системных зависимостей...", "info")
    run(f"apt-get install -y {joined}")

    log("Установка зависимостей завершена", "ok")

if __name__ == "__main__":
    install_dependencies()
