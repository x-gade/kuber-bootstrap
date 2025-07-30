#!/usr/bin/env python3
"""
    Patcher module for updating CiliumNode with assigned CIDR info.
    Supports --cpb mode, --w (worker mode), or external JSON input.

    Модуль Patcher для обновления объекта CiliumNode.
    Поддерживает режимы --cpb (control-plane bootstrap), --w (worker mode) и внешний JSON-файл.
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
WORKER_MAP = Path("cluster/ipam_cilium/maps/worker_map.json")

# kubeconfig для воркера
WORKER_KUBECONFIG = "/etc/kubernetes/admin.conf"

def load_entry_from_cpb() -> dict:
    """
    Load node info from control_plane_map.json using current hostname.
    Загружает данные узла из карты control_plane по текущему hostname.
    """
    hostname = os.uname().nodename
    if not CONTROL_MAP.exists():
        raise FileNotFoundError(f"Файл карты не найден: {CONTROL_MAP}")
    data = json.loads(CONTROL_MAP.read_text())
    if hostname not in data:
        raise KeyError(f"Нода {hostname} не найдена в карте {CONTROL_MAP}")
    return data[hostname]

def load_entry_from_worker() -> dict:
    """
    Load node info from worker_map.json directly (worker mode).
    Загружает данные узла из worker_map.json напрямую (режим worker).
    """
    if not WORKER_MAP.exists():
        raise FileNotFoundError(f"Файл worker_map.json не найден: {WORKER_MAP}")
    return json.loads(WORKER_MAP.read_text())

def load_entry_from_file(path: str) -> dict:
    """
    Load node info from external JSON file.
    Загружает данные узла из внешнего JSON-файла.
    """
    f = Path(path)
    if not f.exists():
        raise FileNotFoundError(f"Файл не найден: {f}")
    return json.loads(f.read_text())

def run_kubectl(cmd: list, use_worker_config=False):
    """
    Run kubectl with optional --kubeconfig for worker node.
    Запускает kubectl с опциональным --kubeconfig для воркер-ноды.
    """
    if use_worker_config:
        cmd = ["kubectl", f"--kubeconfig={WORKER_KUBECONFIG}"] + cmd
    else:
        cmd = ["kubectl"] + cmd

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result

def patch_node(name: str, cidr: str, worker_mode=False):
    """
    Patch Kubernetes node with given CIDR.
    Пропатчить Kubernetes-ноду с указанным CIDR.
    """
    patch_payload = f'{{"spec":{{"podCIDR":"{cidr}"}}}}'
    cmd = [
        "patch", "node", name,
        "--type=merge",
        f"-p={patch_payload}"
    ]

    result = run_kubectl(cmd, use_worker_config=worker_mode)

    if result.returncode == 0:
        log(f"Нода {name} успешно пропатчена CIDR {cidr}", "ok")
    else:
        log(f"Ошибка при патче ноды {name}: {result.stderr.decode()}", "error")
        sys.exit(1)

def patch_cilium_node(name: str, cidr: str, worker_mode=False):
    """
    Patch CiliumNode object with podCIDRs via JSON patch.
    Пропатчить объект CiliumNode, добавив podCIDRs через JSON patch.
    """
    patch = json.dumps([
        {"op": "add", "path": "/spec/ipam", "value": {}},
        {"op": "add", "path": "/spec/ipam/podCIDRs", "value": [cidr]}
    ])

    cmd = [
        "patch", "ciliumnode", name,
        "--type=json",
        "-p", patch
    ]

    result = run_kubectl(cmd, use_worker_config=worker_mode)

    if result.returncode == 0:
        log(f"CiliumNode {name} успешно пропатчен podCIDRs {cidr}", "ok")
    else:
        log(f"Ошибка при патче CiliumNode {name}: {result.stderr.decode()}", "error")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Patch CiliumNode with CIDR info")
    parser.add_argument("--cpb", action="store_true", help="Режим control-plane bootstrap")
    parser.add_argument("--w", action="store_true", help="Режим worker (читает worker_map.json и использует свой kubeconfig)")
    parser.add_argument("--json", help="Путь до JSON-файла с описанием ноды")

    args = parser.parse_args()

    try:
        worker_mode = False

        if args.cpb:
            node_info = load_entry_from_cpb()
        elif args.w:
            node_info = load_entry_from_worker()
            worker_mode = True  # Включаем использование worker kubeconfig
        elif args.json:
            node_info = load_entry_from_file(args.json)
        else:
            parser.error("Укажите --cpb, --w или --json <path>")

        patch_node(node_info["name"], node_info["cidr"], worker_mode=worker_mode)
        patch_cilium_node(node_info["name"], node_info["cidr"], worker_mode=worker_mode)

    except Exception as e:
        log(f"[PATCHER] Ошибка: {str(e)}", "error")
        sys.exit(1)
