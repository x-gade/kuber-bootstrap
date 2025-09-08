#!/usr/bin/env python3
"""
BPF files verifier/installer for Cilium (EN)
    Verifies the presence of required BPF files for Cilium in the target
    directory (/var/lib/cilium/bpf) and complements only the missing files
    from a tar.gz archive (/opt/kuber-bootstrap/binares/bpf.tar.gz).
    The extraction is guarded against path traversal, strips a leading
    "bpf/" prefix to avoid nested "bpf/bpf" structures, and writes only
    the files that are not yet present on disk. All key steps are logged
    via utils.logger.log; critical failures terminate the process.

Проверка/установка BPF-файлов для Cilium (RU)
    Проверяет наличие нужных BPF-файлов в целевой директории
    (/var/lib/cilium/bpf) и дополняет только отсутствующие файлы из архива
    (/opt/kuber-bootstrap/binares/bpf.tar.gz).
    Извлечение защищено от обхода путей (path traversal), срезается
    ведущий префикс "bpf/", чтобы не создавать вложенность "bpf/bpf",
    на диск сохраняются только недостающие файлы. Все этапы логируются
    через utils.logger.log; критические ошибки приводят к завершению работы.
"""

import os
import sys
import tarfile
from pathlib import Path

# Добавляем utils.logger
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from utils.logger import log

# Пути
BPF_ARCHIVE = Path("/opt/kuber-bootstrap/binares/bpf.tar.gz")
# ВАЖНО: целевая директория именно /var/lib/cilium/bpf
BPF_TARGET_DIR = Path("/var/lib/cilium/bpf")


def _normalize_member_path(name: str) -> str:
    """
    Normalize a tar member path to a safe relative path (EN)
        - Strips leading slashes and collapses '.', '..' segments;
        - Removes leading 'bpf/' prefix (case-insensitive) if present;
        - Returns a POSIX-style relative path to be joined under the
          BPF target directory. Empty/invalid results yield "".

        Parameters:
            name: str  - original member name from the tar archive

        Returns:
            str: safe, normalized relative path ("" if not applicable)

    Нормализует путь элемента архива до безопасного относительного (RU)
        - Убирает ведущие слеши и сворачивает сегменты '.', '..';
        - Срезает ведущий префикс 'bpf/' (без учёта регистра), если он есть;
        - Возвращает относительный путь в POSIX-формате для соединения
          с целевой директорией. Пустой/некорректный результат даёт "".

        Параметры:
            name: str  - исходное имя элемента из tar-архива

        Возвращает:
            str: безопасный относительный путь ("" если не применимо)
    """
    # убираем ведущие слеши
    name = name.lstrip("/")

    # разбиваем и фильтруем потенциальные обходы
    parts = []
    for p in name.split("/"):
        if p in ("", ".", ".."):
            continue
        parts.append(p)

    if not parts:
        return ""

    # если верхний уровень равен 'bpf', срезаем его
    if parts[0].lower() == "bpf":
        parts = parts[1:]

    return "/".join(parts)


def extract_missing_files():
    """
    Extract only missing BPF files to the Cilium target directory (EN)
        Compares the normalized content of the archive with the actual files
        under /var/lib/cilium/bpf and extracts only the missing ones.
        - Ensures target directory exists;
        - Builds a list of file candidates from the archive (regular files only);
        - Computes the subset not present on disk;
        - Streams extraction (member-by-member) to the exact normalized paths.

        Side effects:
            - Creates directories as needed under BPF_TARGET_DIR;
            - Logs status and results; exits(1) if the archive is absent.

    Извлекает только недостающие BPF-файлы в целевую директорию Cilium (RU)
        Сравнивает нормализованный список из архива с содержимым
        /var/lib/cilium/bpf и извлекает только отсутствующие файлы.
        - Гарантирует существование целевой директории;
        - Формирует список кандидатов (только обычные файлы);
        - Определяет недостающие на диске;
        - Потоково извлекает каждый недостающий файл в нормализованный путь.

        Побочные эффекты:
            - Создаёт директории внутри BPF_TARGET_DIR по мере необходимости;
            - Логирует ход и результат; завершает работу (exit 1), если архив не найден.
    """
    if not BPF_ARCHIVE.exists():
        log(f"Архив с BPF-файлами не найден: {BPF_ARCHIVE}", "error")
        sys.exit(1)

    # Создаём целевую директорию при необходимости
    if not BPF_TARGET_DIR.exists():
        log(f"Целевая директория {BPF_TARGET_DIR} не существует — создаём...", "warn")
        BPF_TARGET_DIR.mkdir(parents=True, exist_ok=True)

    with tarfile.open(BPF_ARCHIVE, "r:gz") as tar:
        # Список кандидатов (только обычные файлы), уже нормализованный
        candidates = []
        for m in tar.getmembers():
            if not m.isfile():
                continue
            relpath = _normalize_member_path(m.name)
            if not relpath:
                continue
            candidates.append((m, relpath))

        # Определим, какие именно файлы отсутствуют на диске
        missing = []
        for m, relpath in candidates:
            target_file = BPF_TARGET_DIR / relpath
            if not target_file.exists():
                missing.append((m, relpath))

        if not missing:
            log("Все BPF-файлы уже на месте, дополнять нечего", "ok")
            return

        log(f"Найдено недостающих файлов: {len(missing)}. Добавляем...", "info")

        # Извлекаем только недостающие с нормализацией путей
        for m, relpath in missing:
            target_file = BPF_TARGET_DIR / relpath
            target_file.parent.mkdir(parents=True, exist_ok=True)
            # извлекаем потоково, чтобы не тащить оригинальную структуру «как есть»
            with tar.extractfile(m) as src, open(target_file, "wb") as dst:
                dst.write(src.read())
            log(f"Добавлен файл: {relpath}", "ok")


def main():
    """
    Entry point for BPF files verification/installation (EN)
        Logs the start, runs extraction of missing files, and logs completion.
        Exits are handled inside extract_missing_files() where appropriate.

    Точка входа проверки/установки BPF-файлов (RU)
        Логирует старт, вызывает извлечение недостающих файлов и логирует завершение.
        Завершение по ошибкам обрабатывается внутри extract_missing_files().
    """
    log("=== Проверка и установка BPF-файлов Cilium ===", "info")
    extract_missing_files()
    log("Проверка/установка BPF-файлов завершена", "ok")


if __name__ == "__main__":
    main()
