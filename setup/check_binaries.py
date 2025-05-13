# setup/check_binaries.py

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import yaml
import shutil
import json
from utils.logger import log
from data import collected_info

REQUIRED_FILE = "data/required_binaries.yaml"
MISSING_OUTPUT = "data/missing_binaries.json"

def load_required_binaries(role):
    with open(REQUIRED_FILE, "r") as f:
        all_binaries = yaml.safe_load(f)
    return all_binaries.get(role, [])

def check_binary(binary):
    path = shutil.which(binary)
    if path:
        log(f"{binary} найден: {path}", "ok")
        return True
    else:
        log(f"{binary} не найден", "warn")
        return False

def check_all_binaries():
    role = collected_info.ROLE
    log(f"Проверка бинарников для роли: {role}", "info")
    required = load_required_binaries(role)
    missing = []

    for binary in required:
        if not check_binary(binary):
            missing.append(binary)

    if missing:
        with open(MISSING_OUTPUT, "w") as f:
            json.dump({"missing": missing}, f, indent=2)
        log(f"Отсутствуют: {', '.join(missing)}", "error")
    else:
        if os.path.exists(MISSING_OUTPUT):
            os.remove(MISSING_OUTPUT)
        log("Все бинарники на месте", "ok")

    return missing

if __name__ == "__main__":
    check_all_binaries()
