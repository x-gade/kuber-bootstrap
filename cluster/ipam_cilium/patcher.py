#!/usr/bin/env python3
"""
    Patcher module for updating CiliumNode with assigned CIDR info.
    Supports --cpb mode or external JSON input.

    Модуль Patcher для обновления объекта CiliumNode.
    Поддерживает режим bootstrap (--cpb) или внешний JSON-файл.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Добавляем корень проекта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from utils.logger import log

CONTROL_MAP = Path("cluster/ipam_cilium/maps/control_plane_map.json")

def load_entry_from_cpb() -> dict:
    """
        Load node info from control_plane_map.json using current hostname

        Загружает данные узла из карты control_plane по текущему hostname
    """
    hostname = os.uname().nodename
    if not CONTROL_MAP.exists():
        raise FileNotFoundError(f"Файл карты не найден: {CONTROL_MAP}")
    data = json.loads(CONTROL_MAP.read_text())
    if hostname not in data:
        raise KeyError(f"Нода {hostname} не найдена в карте {CONTROL_MAP}")
    return data[hostname]

def load_entry_from_file(path: str) -> dict:
    """
        Load node info from external JSON file

        Загружает данные узла из внешнего JSON-файла
    """
    f = Path(path)
    if not f.exists():
        raise FileNotFoundError(f"Файл не найден: {f}")
    return json.loads(f.read_text())

def patch_node(name: str, cidr: str):
    """
        Patch Kubernetes node with given CIDR

        Пропатчить Kubernetes-ноду с указанным CIDR
    """
    patch_cmd = [
        "kubectl", "patch", "node", name,
        "--type=merge",
        f"-p={{\"spec\":{{\"podCIDR\":\"{cidr}\"}}}}"
    ]
    result = subprocess.run(patch_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode == 0:
        log(f"Нода {name} успешно пропатчена CIDR {cidr}", "ok")
    else:
        log(f"Ошибка при патче ноды {name}: {result.stderr.decode()}", "error")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Patch CiliumNode with CIDR info")
    parser.add_argument("--cpb", action="store_true", help="Режим control-plane bootstrap")
    parser.add_argument("--json", help="Путь до JSON-файла с описанием ноды")

    args = parser.parse_args()

    try:
        if args.cpb:
            node_info = load_entry_from_cpb()
        elif args.json:
            node_info = load_entry_from_file(args.json)
        else:
            parser.error("Укажите --cpb или --json <path>")

        patch_node(node_info["name"], node_info["cidr"])

    except Exception as e:
        log(f"[PATCHER] Ошибка: {str(e)}", "error")
        sys.exit(1)
