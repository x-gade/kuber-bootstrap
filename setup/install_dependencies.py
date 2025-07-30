#!/usr/bin/env python3
"""
Installs essential system dependencies for Kubernetes node initialization.
Устанавливает системные зависимости для инициализации узла Kubernetes.
"""

import os
import sys
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log

BASE_PACKAGES = [
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

BPFTOOL_DEPENDENCIES = [
    "libelf1",
    "zlib1g",
    "libcap2",
    "libc6"
]

def run(cmd: str):
    """
    Execute a shell command and exit on failure.
    Выполняет команду оболочки и завершает работу при ошибке.
    """
    log(f"Выполняю: {cmd}", "info")
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        log(f"Ошибка при выполнении: {e}", "error")
        sys.exit(1)

def install_linux_tools():
    """
    Install bpftool by installing linux-tools for current kernel.
    Устанавливает bpftool через пакет linux-tools для текущего ядра.
    """
    uname = subprocess.check_output("uname -r", shell=True).decode().strip()
    tools_pkg = f"linux-tools-{uname}"
    log(f"Определено ядро: {uname}, ставим {tools_pkg}", "info")

    run("apt-get install -y linux-tools-generic")
    run(f"apt-get install -y {tools_pkg}")

    result = subprocess.run("find /usr/lib/linux-tools-* -name bpftool | head -n 1", shell=True, capture_output=True, text=True)
    bpftool_path = result.stdout.strip()
    if bpftool_path:
        if not os.path.exists("/usr/local/bin/bpftool"):
            run(f"ln -s {bpftool_path} /usr/local/bin/bpftool")
        log(f"bpftool установлен: {bpftool_path}", "ok")
    else:
        log("bpftool не найден после установки linux-tools!", "error")
        sys.exit(1)

def install_dependencies():
    """
    Install base system dependencies + bpftool + runtime shared libraries.
    Устанавливает базовые зависимости + bpftool + runtime-библиотеки.
    """
    log("Обновление списка пакетов...", "info")
    run("apt-get update")

    # Основные пакеты
    joined_base = " ".join(BASE_PACKAGES)
    log(f"Установка базовых системных зависимостей: {joined_base}", "info")
    run(f"apt-get install -y {joined_base}")

    # Зависимости bpftool
    joined_libs = " ".join(BPFTOOL_DEPENDENCIES)
    log(f"Установка библиотек зависимостей для bpftool: {joined_libs}", "info")
    run(f"apt-get install -y {joined_libs}")

    # Сама утилита
    log("Устанавливаем bpftool через linux-tools...", "info")
    install_linux_tools()

    log("Установка всех зависимостей завершена", "ok")

if __name__ == "__main__":
    install_dependencies()
