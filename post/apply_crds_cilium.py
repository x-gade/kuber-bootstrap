"""
Apply all Cilium CRDs from the local directory using kubectl.
Применяет все CRD-файлы Cilium из локальной папки с помощью kubectl.
"""

import os
import sys
import subprocess
import glob

# Добавляем корень проекта в PYTHONPATH, чтобы работал импорт utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log

# Путь к директории, где лежат CRD-файлы (возможно, с поддиректориями)
CRD_DIR = "/opt/kuber-bootstrap/data/crds"

def apply_crd(file_path: str) -> bool:
    """
    Apply a single CRD file using kubectl.
    Применяет один CRD-файл с помощью kubectl.
    """
    try:
        result = subprocess.run(
            ["kubectl", "apply", "-f", file_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        log(f"[{os.path.basename(file_path)}] {result.stdout.decode().strip()}", "ok")
        return True
    except subprocess.CalledProcessError as e:
        log(f"[{os.path.basename(file_path)}] Failed to apply:\n{e.stderr.decode().strip()}", "error")
        return False

def apply_all_crds():
    """
    Apply all CRD YAML files found recursively in the CRD directory.
    Применяет все CRD-файлы, найденные рекурсивно в директории CRD.
    """
    if not os.path.isdir(CRD_DIR):
        log(f"CRD directory not found: {CRD_DIR}", "error")
        return

    # Ищем рекурсивно все .yaml/.yml файлы
    crd_files = sorted(glob.glob(os.path.join(CRD_DIR, "**", "*.y*ml"), recursive=True))

    if not crd_files:
        log("No CRD files found in the directory", "warn")
        return

    log(f"Found {len(crd_files)} CRD files. Starting to apply...", "info")
    for crd_file in crd_files:
        apply_crd(crd_file)

if __name__ == "__main__":
    apply_all_crds()
