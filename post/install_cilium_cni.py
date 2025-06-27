#!/usr/bin/env python3
"""
Checks for cilium-cni binary and conflist, installs or generates as needed.
Проверяет наличие бинарника cilium-cni и конфигурации conflist,
при необходимости устанавливает или создаёт.
"""

import os
import tarfile
import shutil
import sys
from pathlib import Path
from jinja2 import Template

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log

# Пути
ARCHIVE_PATH = Path("/opt/kuber-bootstrap/binares/cilium-cni.tar.gz")
EXTRACT_DIR = Path("/opt/kuber-bootstrap/tmp/cilium_cni_extract")
INSTALL_BIN_PATH = Path("/opt/cni/bin/cilium-cni")
CONFLIST_TEMPLATE_PATH = Path("data/cni/cilium.conflist.j2")
CONFLIST_OUTPUT_PATH = Path("/etc/cni/net.d/10-cilium.conflist")
COLLECTED_INFO_MODULE = Path("data/collected_info.py")

def load_collected_info() -> dict:
    """
    Imports collected_info from Python module.
    Импортирует переменные из файла data/collected_info.py как словарь.
    """
    import importlib.util

    module_path = COLLECTED_INFO_MODULE.resolve()
    spec = importlib.util.spec_from_file_location("collected_info", str(module_path))
    collected = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collected)

    return {
        "IP": collected.IP,
        "HOSTNAME": collected.HOSTNAME,
        "ARCH": collected.ARCH,
        "DISTRO": collected.DISTRO,
        "KERNEL": collected.KERNEL,
        "ROLE": collected.ROLE,
        "CIDR": collected.CIDR,
        "CLUSTER_POD_CIDR": collected.CLUSTER_POD_CIDR,
    }

def extract_archive() -> None:
    """
    Extracts the Cilium CNI archive to a temporary directory.
    Распаковывает архив Cilium CNI во временную директорию.
    """
    log("Распаковка архива cilium-cni...", "info")
    with tarfile.open(ARCHIVE_PATH, "r:gz") as tar:
        tar.extractall(path=EXTRACT_DIR)
    log(f"Архив распакован в {EXTRACT_DIR}", "ok")

def install_binary() -> bool:
    """
    Installs the cilium-cni binary to /opt/cni/bin.
    Устанавливает бинарный файл cilium-cni в /opt/cni/bin.
    """
    binary_path = EXTRACT_DIR / "cilium-cni" / "cilium-cni"
    if not binary_path.exists():
        log(f"Бинарник не найден: {binary_path}", "error")
        return False

    INSTALL_BIN_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary_path, INSTALL_BIN_PATH)
    os.chmod(INSTALL_BIN_PATH, 0o755)
    log(f"Бинарник установлен: {INSTALL_BIN_PATH}", "ok")
    return True

def cleanup() -> None:
    """
    Deletes the temporary extraction directory.
    Удаляет временную директорию распаковки.
    """
    if EXTRACT_DIR.exists():
        shutil.rmtree(EXTRACT_DIR)
        log(f"Удалена временная директория: {EXTRACT_DIR}", "info")

def render_conflist(collected: dict) -> None:
    """
    Renders the 10-cilium.conflist configuration using a Jinja2 template.
    Генерирует конфигурацию 10-cilium.conflist из шаблона и сохраняет её.
    """
    log("Генерация конфигурации /etc/cni/net.d/10-cilium.conflist...", "info")
    with open(CONFLIST_TEMPLATE_PATH, "r") as f:
        template = Template(f.read())

    output = template.render(
        public_ip=collected["IP"],
        service_port="6443",
        pod_cidr=collected["CLUSTER_POD_CIDR"]
    )

    CONFLIST_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFLIST_OUTPUT_PATH, "w") as f:
        f.write(output)
    log(f"Конфигурация записана: {CONFLIST_OUTPUT_PATH}", "ok")

def main() -> None:
    """
    Main logic: installs binary and generates config if missing.
    Основная логика: установка бинаря и генерация конфига при необходимости.
    """
    collected = load_collected_info()

    # Бинарник
    if INSTALL_BIN_PATH.exists():
        log("Cilium CNI бинарник уже установлен", "warn")
    else:
        log("Cilium CNI не найден — установка", "info")
        extract_archive()
        if install_binary():
            cleanup()
        else:
            log("Установка прервана: бинарник не найден после распаковки", "error")
            return

    # Конфигурация
    if CONFLIST_OUTPUT_PATH.exists():
        log("Файл конфигурации уже существует", "warn")
    else:
        render_conflist(collected)

if __name__ == "__main__":
    main()
