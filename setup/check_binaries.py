#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Binary presence checker for kube-bootstrap pipeline.
Проверка наличия бинарников для пайплайна kube-bootstrap.
"""

import sys
import os
import shutil
import json
import yaml
from pathlib import Path

# === Project paths bootstrap ===
# Добавляем путь к корню проекта для импорта модулей
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log  # noqa: E402
from data import collected_info  # noqa: E402


# === Constants ===
REQUIRED_FILE = Path("data/required_binaries.yaml")
MISSING_OUTPUT = Path("data/missing_binaries.json")
INSTALL_PATH = Path("/usr/local/bin")

# CNI
CNI_BIN_DIR = Path("/opt/cni/bin")
# Минимальный обязательный плагин CNI — loopback. Без него sandbox не создаётся.
CNI_REQUIRED = ["loopback"]


def load_required_binaries(role: str):
    """
    Load required binaries list from YAML based on node role.
    Загружает список требуемых бинарников из YAML по роли узла.
    """
    if not REQUIRED_FILE.exists():
        log(f"Файл со списком бинарников не найден: {REQUIRED_FILE}", "error")
        return []

    try:
        with REQUIRED_FILE.open("r", encoding="utf-8") as f:
            all_binaries = yaml.safe_load(f) or {}
    except Exception as e:
        log(f"Ошибка чтения {REQUIRED_FILE}: {e}", "error")
        return []

    binaries = all_binaries.get(role, [])
    if not isinstance(binaries, list):
        log(f"Некорректный формат для роли '{role}' в {REQUIRED_FILE}", "error")
        return []

    if not binaries:
        log(f"Роль '{role}' не определена или пустая в {REQUIRED_FILE}", "error")

    return binaries


def is_installed(binary: str) -> bool:
    """
    Check if a CLI binary exists in PATH or in the install directory.
    Проверяет, установлен ли CLI-бинарник в PATH или в /usr/local/bin.
    """
    return shutil.which(binary) is not None or (INSTALL_PATH / binary).exists()


def cni_plugins_installed() -> bool:
    """
    Return True if essential CNI plugins are present in /opt/cni/bin.
    Возвращает True, если базовые CNI-плагины присутствуют в /opt/cni/bin.
    """
    if not CNI_BIN_DIR.is_dir():
        return False
    for name in CNI_REQUIRED:
        if not (CNI_BIN_DIR / name).exists():
            return False
    return True


def write_missing_file(missing: list) -> None:
    """
    Persist missing binaries list to JSON (atomic replace).
    Сохраняет список отсутствующих бинарников в JSON (атомарная замена).
    """
    tmp_path = MISSING_OUTPUT.with_suffix(".json.tmp")
    try:
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump({"missing": missing}, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, MISSING_OUTPUT)
        log(f"Список отсутствующих бинарников сохранён в {MISSING_OUTPUT}", "warn")
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


def check_all_binaries(role: str | None = None) -> list:
    """
    Main entry: check presence of required binaries for a given node role.
    Основная точка входа: проверяет наличие требуемых бинарников для роли узла.
    """
    role = role or getattr(collected_info, "ROLE", None)
    if not role:
        log("Не удалось определить роль узла (передайте CLI-аргумент или настройте collected_info.ROLE)", "error")
        return []

    log(f"Проверка бинарников для роли: {role}", "info")

    required = load_required_binaries(role)
    missing: list[str] = []

    # --- Special handling: CNI plugins marker ---
    # Если в YAML указан маркер "cni-plugins", проверяем наличие базовых плагинов в /opt/cni/bin.
    if "cni-plugins" in required:
        if cni_plugins_installed():
            log("CNI plugins: OK (/opt/cni/bin/loopback найден)", "ok")
        else:
            log("CNI plugins: отсутствуют (нет /opt/cni/bin/loopback)", "warn")
            missing.append("cni-plugins")
        # Убираем маркер из списка, чтобы не искать его в PATH как обычный бинарь
        required = [b for b in required if b != "cni-plugins"]

    # --- Regular CLI binaries ---
    for binary in required:
        if is_installed(binary):
            log(f"{binary} установлен", "ok")
        else:
            log(f"{binary} отсутствует", "warn")
            missing.append(binary)

    # --- Persist result / cleanup ---
    if missing:
        write_missing_file(missing)
    else:
        if MISSING_OUTPUT.exists():
            try:
                MISSING_OUTPUT.unlink()
            except Exception as e:
                log(f"Не удалось удалить {MISSING_OUTPUT}: {e}", "warn")
        log("Все бинарники присутствуют", "ok")

    return missing


def _parse_role_from_argv() -> str | None:
    """
    Parse node role from CLI args (single optional positional argument).
    Извлекает роль узла из CLI-аргументов (один необязательный позиционный аргумент).
    """
    return sys.argv[1] if len(sys.argv) > 1 else None


if __name__ == "__main__":
    """
    CLI entrypoint.
    Точка входа при запуске из командной строки.
    """
    role_arg = _parse_role_from_argv()
    check_all_binaries(role_arg)
