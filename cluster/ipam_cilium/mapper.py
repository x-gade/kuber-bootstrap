#!/usr/bin/env python3
"""
    Mapper module for assigning static CIDR blocks to Kubernetes nodes.
    Supports both manual input and bootstrap mode (cpb).

    Модуль Mapper для назначения CIDR блоков узлам Kubernetes.
    Поддерживает ручной режим и bootstrap-режим (cpb).
"""

import argparse
import json
import sys
import os
from ipaddress import IPv4Network, IPv4Address
from pathlib import Path

# Добавляем корень проекта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from utils.logger import log

# Базовая директория карт
MAPS_DIR = Path("cluster/ipam_cilium/maps")
MAPS_DIR.mkdir(parents=True, exist_ok=True)

# Пути до JSON файлов карт
CONTROL_MAP = MAPS_DIR / "control_plane_map.json"
WORKER_MAP = MAPS_DIR / "worker_map.json"
COLLECTED_INFO = Path("data/collected_info.py")

def load_map(path: Path) -> dict:
    """
        Load JSON map from file

        Загружает JSON-карту из файла
    """
    if not path.exists():
        path.write_text("{}")
    return json.loads(path.read_text())

def save_map(path: Path, data: dict) -> None:
    """
        Save JSON map to file

        Сохраняет JSON-карту в файл
    """
    path.write_text(json.dumps(data, indent=4))

def extract_info_from_py() -> tuple[str, str, str]:
    """
        Extract node information from collected_info.py

        Извлекает параметры ноды из collected_info.py
    """
    namespace = {}
    exec(COLLECTED_INFO.read_text(), namespace)
    return (
        namespace["HOSTNAME"],
        namespace["IP"],
        namespace["ROLE"]
    )

def find_next_subnet(base: IPv4Network, used: set[str], mask: int, role: str) -> tuple[str, str]:
    """
        Find next unused subnet in base network and return its CIDR and clasterip

        Находит следующую неиспользуемую подсеть в базовой сети
        и возвращает её CIDR и clasterip
    """
    available = list(base.subnets(new_prefix=mask))

    for subnet in available:
        cidr = str(subnet)
        if cidr in used:
            continue

        if role == "control-plane":
            # clasterip: фиксированная сеть 10.244.0.X
            offset = int(subnet.network_address.exploded.split(".")[-1])
            clasterip = f"10.244.0.{offset}"
        else:
            clasterip = str(subnet.network_address)

        return cidr, clasterip

    raise RuntimeError("CIDR pool exhausted")

def assign_cidr(role: str, nodename: str, globalip: str) -> dict:
    """
        Assign next free CIDR block to a node and update map

        Назначает следующий CIDR блок ноде и обновляет карту
    """
    if role == "control-plane":
        path = CONTROL_MAP
        base = IPv4Network("10.244.0.0/26")
        mask = 26
    elif role == "worker":
        path = WORKER_MAP
        base = IPv4Network("10.244.1.0/24")
        mask = 24
    else:
        raise ValueError(f"Unknown role: {role}")

    data = load_map(path)

    if nodename in data:
        log(f"Нода {nodename} уже присутствует в карте", "warn")
        print(json.dumps(data[nodename], indent=4))
        return data[nodename]

    used_cidrs = {entry["cidr"] for entry in data.values()}
    cidr, clasterip = find_next_subnet(base, used_cidrs, mask, role)

    entry = {
        "role": role,
        "name": nodename,
        "globalip": globalip,
        "cidr": cidr,
        "clasterip": clasterip
    }

    data[nodename] = entry
    save_map(path, data)

    log(f"Добавлен узел {nodename} в карту {path.name}", "ok")
    print(json.dumps(entry, indent=4))
    return entry

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assign CIDR to a Kubernetes node")

    parser.add_argument("--cpb", action="store_true",
                        help="Use collected_info.py to get node parameters")
    parser.add_argument("--name", help="Node hostname")
    parser.add_argument("--ip", help="Node global IP")
    parser.add_argument("--role", choices=["control-plane", "worker"], help="Node role")

    args = parser.parse_args()

    if args.cpb:
        name, ip, role = extract_info_from_py()
    else:
        if not (args.name and args.ip and args.role):
            parser.error("Must provide --name, --ip and --role unless using --cpb")
        name, ip, role = args.name, args.ip, args.role

    assign_cidr(role, name, ip)
