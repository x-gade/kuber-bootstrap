#!/usr/bin/env python3
"""
Проверка и подготовка маунтов BPF и cgroup2 для работы Cilium
Mount and prepare BPF and cgroup2 paths required by Cilium
"""

import os
import subprocess
import sys
from shutil import which
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from utils.logger import log


def is_mounted(path: str) -> bool:
    """
    Проверяет, смонтирован ли указанный путь
    Check if the given mount point is currently mounted
    """

    with open('/proc/mounts', 'r') as f:
        return any(line.split()[1] == path for line in f)


def get_mount_type(path: str) -> str | None:
    """
    Возвращает тип файловой системы для маунта по пути (если есть)
    Return the filesystem type for the given mount path, if mounted
    """

    with open('/proc/mounts', 'r') as f:
        for line in f:
            parts = line.split()
            if parts[1] == path:
                return parts[2]
    return None


def mount_bpf():
    """
    Проверяет и монтирует bpffs в /sys/fs/bpf при необходимости
    Ensure /sys/fs/bpf is mounted as bpffs, create if needed
    """

    path = "/sys/fs/bpf"
    fstab_entry = "bpffs /sys/fs/bpf bpf defaults 0 0"

    if not Path(path).exists():
        log(f"{path} не существует — создаём...", "warn")
        os.makedirs(path, exist_ok=True)

    if not is_mounted(path):
        log(f"Монтируем bpffs в {path}...", "info")
        subprocess.run(["mount", "-t", "bpf", "bpffs", path], check=True)
    elif get_mount_type(path) != "bpf":
        log(f"{path} смонтирован не как bpffs — требуется вмешательство.", "error")
        sys.exit(1)
    else:
        log(f"{path} уже корректно смонтирован.", "ok")

    # Проверим, есть ли запись в /etc/fstab
    with open("/etc/fstab", "r") as f:
        lines = f.readlines()

    if any(fstab_entry in line for line in lines):
        log("Запись для bpffs уже есть в /etc/fstab", "ok")
    else:
        log("Добавляем запись в /etc/fstab для постоянного маунта bpffs", "info")
        with open("/etc/fstab", "a") as f:
            f.write(fstab_entry + "\n")



def mount_cgroupv2():
    """
    Проверяет и монтирует cgroup2 в /run/cilium/cgroupv2 при необходимости
    Ensure /run/cilium/cgroupv2 is mounted as cgroup2, create if needed
    """

    path = "/run/cilium/cgroupv2"
    if not Path(path).exists():
        log(f"{path} не существует — создаём...", "warn")
        os.makedirs(path, exist_ok=True)

    if not is_mounted(path):
        log(f"Монтируем cgroup2 в {path}...", "info")
        subprocess.run(["mount", "-t", "cgroup2", "none", path], check=True)
    elif get_mount_type(path) != "cgroup2":
        log(f"{path} смонтирован не как cgroup2 — требуется вмешательство.", "error")
        sys.exit(1)
    else:
        log(f"{path} уже корректно смонтирован.", "ok")


def bpftool_check():
    """
    Проверяет наличие утилиты bpftool и выводит информацию о загруженных BPF-объектах
    Check for bpftool and display current BPF programs and maps if available
    """

    if which("bpftool") is None:
        log("bpftool не найден — пропускаем BPF-инвентаризацию.", "warn")
        return

    log("Загруженные BPF-программы:", "info")
    subprocess.run(["bpftool", "prog", "show"])

    log("BPF-карты:", "info")
    subprocess.run(["bpftool", "map", "show"])


def main():
    """
    Основная точка входа — проверяет и подготавливает окружение для Cilium
    Main entry point — validate and prepare BPF and cgroup mounts for Cilium
    """

    log("Начинаем проверку маунтов BPF и CGroup2", "info")
    mount_bpf()
    mount_cgroupv2()
    bpftool_check()
    log("Проверка маунтов завершена успешно.", "ok")


if __name__ == "__main__":
    main()
