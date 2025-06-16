# setup/check_binaries.py

import sys
import os
import shutil
import json
import yaml
from pathlib import Path

# Добавляем путь к корню проекта для импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data import collected_info

REQUIRED_FILE = "data/required_binaries.yaml"
MISSING_OUTPUT = "data/missing_binaries.json"
INSTALL_PATH = "/usr/local/bin"

def load_required_binaries(role):
    """
    Load required binaries list from YAML based on node role.
    Загружает список требуемых бинарников из YAML по роли узла.
    """
    with open(REQUIRED_FILE, "r") as f:
        all_binaries = yaml.safe_load(f)
    binaries = all_binaries.get(role, [])
    if not binaries:
        log(f"Роль '{role}' не определена в {REQUIRED_FILE}", "error")
        return []
    return binaries

def is_installed(binary: str) -> bool:
    """
    Check if a binary exists in system PATH or in the install directory.
    Проверяет, установлен ли бинарник в системе или в /usr/local/bin.
    """
    return shutil.which(binary) is not None or Path(INSTALL_PATH, binary).exists()

def check_all_binaries(role=None):
    """
    Main logic: check presence of required binaries for the given node role.
    Основная логика: проверяет наличие нужных бинарников для указанной роли.
    """
    role = role or collected_info.ROLE
    log(f"Проверка бинарников для роли: {role}", "info")

    required = load_required_binaries(role)
    missing = []

    for binary in required:
        if is_installed(binary):
            log(f"{binary} установлен", "ok")
        else:
            log(f"{binary} отсутствует", "warn")
            missing.append(binary)

    if missing:
        with open(MISSING_OUTPUT, "w") as f:
            json.dump({"missing": missing}, f, indent=2)
        log(f"Список отсутствующих бинарников сохранён в {MISSING_OUTPUT}", "warn")
    else:
        if os.path.exists(MISSING_OUTPUT):
            os.remove(MISSING_OUTPUT)
        log("Все бинарники присутствуют", "ok")

    return missing

if __name__ == "__main__":
    # Поддержка аргумента роли через CLI
    role_arg = sys.argv[1] if len(sys.argv) > 1 else None
    check_all_binaries(role_arg)
