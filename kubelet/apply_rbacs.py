#!/usr/bin/env python3
"""
Apply all RBAC-related YAML manifests using kubectl.
Применяет все YAML-манифесты из data/yaml/rbac через kubectl apply -f
"""

import subprocess
from pathlib import Path
import sys
import os

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log

RBAC_PATH = Path("data/yaml/rbac")

def apply_rbac_manifests():
    if not RBAC_PATH.exists():
        log(f"Директория {RBAC_PATH} не существует", "error")
        return

    yaml_files = sorted(RBAC_PATH.glob("*.yaml"))

    if not yaml_files:
        log(f"Нет RBAC-файлов в {RBAC_PATH}", "warn")
        return

    for file in yaml_files:
        log(f"Применение: {file}", "info")
        result = subprocess.run(
            ["kubectl", "apply", "-f", str(file)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            log(result.stdout.strip(), "ok")
        else:
            log(f"[Ошибка] {file}:\n{result.stderr.strip()}", "error")
            exit(result.returncode)

if __name__ == "__main__":
    apply_rbac_manifests()
