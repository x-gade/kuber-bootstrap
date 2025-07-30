#!/usr/bin/env python3
"""
Проверяет наличие BPF-файлов для Cilium и дополняет недостающие из архива.
Check if BPF object files for Cilium are installed, unpack only missing files.
"""

import os
import sys
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

# Добавляем utils.logger
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from utils.logger import log

# Пути
BPF_ARCHIVE = Path("/opt/kuber-bootstrap/binares/bpf.tar.gz")
BPF_TARGET_DIR = Path("/var/lib/cilium/bpf")

def extract_missing_files():
    """
    Сравнивает содержимое архива с целевой директорией
    и добавляет только недостающие файлы.
    Compare archive contents with target dir and extract only missing files.
    """
    if not BPF_ARCHIVE.exists():
        log(f"Архив с BPF-файлами не найден: {BPF_ARCHIVE}", "error")
        sys.exit(1)

    # Создаём директорию, если нет
    if not BPF_TARGET_DIR.exists():
        log(f"Целевая директория {BPF_TARGET_DIR} не существует — создаём...", "warn")
        BPF_TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # Получаем список файлов в архиве
    with tarfile.open(BPF_ARCHIVE, "r:gz") as tar:
        archive_files = [m.name for m in tar.getmembers() if m.isfile()]

        # Файлы, которых нет в целевой директории
        missing_files = []
        for file_name in archive_files:
            target_file = BPF_TARGET_DIR / file_name
            if not target_file.exists():
                missing_files.append(file_name)

        if not missing_files:
            log("Все BPF-файлы уже на месте, дополнять нечего", "ok")
            return

        log(f"Найдено недостающих файлов: {len(missing_files)}. Добавляем...", "info")

        # Распаковываем только недостающие
        for member in tar.getmembers():
            if member.name in missing_files:
                tar.extract(member, BPF_TARGET_DIR)
                log(f"Добавлен файл: {member.name}", "ok")

def main():
    """
    Основная точка входа:
    1. Проверяет целевую директорию
    2. Добавляет недостающие BPF-файлы из архива
    """
    log("=== Проверка и установка BPF-файлов Cilium ===", "info")
    extract_missing_files()
    log("Проверка/установка BPF-файлов завершена", "ok")

if __name__ == "__main__":
    main()
