#!/usr/bin/env python3
"""
Mapper module for assigning and removing static CIDR blocks for Kubernetes nodes.

Модуль Mapper для назначения и удаления CIDR блоков узлам Kubernetes.
Поддерживает два режима:
  - register (назначить CIDR)
  - delete (удалить ноду из карты)
"""

import argparse
import json
import sys
import os
import ipaddress
from ipaddress import IPv4Network
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


def ensure_map_file(path: Path):
    """
    Ensure the map file exists, create empty if missing
    Гарантирует наличие карты, создаёт пустую если её нет
    """
    if not path.exists():
        log(f"Карта {path.name} отсутствует – создаём новую", "warn")
        path.write_text("{}")


def load_map(path: Path) -> dict:
    """
    Load JSON map from file, ensure it exists

    Загружает JSON-карту из файла, гарантирует её существование
    """
    ensure_map_file(path)
    try:
        return json.loads(path.read_text())
    except Exception as e:
        log(f"Ошибка чтения карты {path.name}: {e}", "error")
        # если повреждена – пересоздаём
        path.write_text("{}")
        return {}


def save_map(path: Path, data: dict) -> None:
    """
    Save JSON map to file in sorted order by CIDR

    Сохраняет JSON-карту в файл с сортировкой по CIDR
    """
    # сортируем по IPv4Network(data[n]["cidr"])
    sorted_items = sorted(
        data.items(),
        key=lambda x: ipaddress.IPv4Network(x[1]["cidr"]).network_address
    )
    sorted_data = {k: v for k, v in sorted_items}

    path.write_text(json.dumps(sorted_data, indent=4))


def extract_info_from_py() -> tuple[str, str, str, str]:
    """
    Extract node information from collected_info.py

    Извлекает параметры ноды из collected_info.py
    """
    namespace = {}
    exec(COLLECTED_INFO.read_text(), namespace)
    return (
        namespace["HOSTNAME"],
        namespace["IP"],
        namespace["ROLE"],
        namespace["CLUSTER_POD_CIDR"]
    )


def get_cluster_pod_cidr() -> IPv4Network:
    """
    Get cluster-wide Pod CIDR from collected_info.py

    Получает общекластерный Pod CIDR из collected_info.py
    """
    namespace = {}
    exec(COLLECTED_INFO.read_text(), namespace)
    cidr = namespace.get("CLUSTER_POD_CIDR")
    if not cidr:
        raise ValueError("CLUSTER_POD_CIDR not found in collected_info.py")
    return IPv4Network(cidr)


def find_next_subnet(base: IPv4Network, used: set[str], mask: int, role: str) -> tuple[str, str]:
    """
    Find next unused subnet in base network and return its CIDR and clasterip

    Находит следующую неиспользуемую подсеть в базовой сети
    и возвращает её CIDR и clasterip
    """
    available = list(base.subnets(new_prefix=mask))

    # Если worker – пропускаем первый блок (10.244.0.0/24)
    if role == "worker" and available:
        available = available[1:]

    for subnet in available:
        cidr = str(subnet)
        if cidr in used:
            continue

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
        base = IPv4Network("10.244.0.0/24")  # вся /24 выделена под control-plane
        mask = 26                            # каждой control-plane выдаём /26
    elif role == "worker":
        path = WORKER_MAP
        cluster_base = get_cluster_pod_cidr()  # читаем из collected_info.py, например 10.244.0.0/16
        mask = 24                              # воркеру выдаём отдельную /24
        base = cluster_base
    else:
        raise ValueError(f"Unknown role: {role}")

    # загружаем карту (создаётся если нет)
    data = load_map(path)

    # если нода уже есть – возвращаем старую запись
    if nodename in data:
        log(f"Нода {nodename} уже присутствует в карте {path.name}", "warn")
        return data[nodename]

    # собираем список уже занятых CIDR
    used_cidrs = {entry["cidr"] for entry in data.values()}

    # ищем следующую свободную
    cidr, clasterip = find_next_subnet(base, used_cidrs, mask, role)

    entry = {
        "role": role,
        "name": nodename,
        "globalip": globalip,
        "cidr": cidr,
        "clasterip": clasterip
    }

    # добавляем и сохраняем
    data[nodename] = entry
    save_map(path, data)

    log(f"Добавлен узел {nodename} в карту {path.name} с CIDR {cidr}", "ok")
    return entry


def delete_node_entry(nodename: str) -> bool:
    """
    Delete a node from control-plane or worker map

    Удаляет ноду из карты control-plane или worker
    """
    deleted = False

    # пробуем удалить из control-plane карты
    cp_data = load_map(CONTROL_MAP)
    if nodename in cp_data:
        del cp_data[nodename]
        save_map(CONTROL_MAP, cp_data)
        log(f"Нода {nodename} удалена из control_plane_map.json", "ok")
        deleted = True

    # пробуем удалить из worker карты
    worker_data = load_map(WORKER_MAP)
    if nodename in worker_data:
        del worker_data[nodename]
        save_map(WORKER_MAP, worker_data)
        log(f"Нода {nodename} удалена из worker_map.json", "ok")
        deleted = True

    if not deleted:
        log(f"Нода {nodename} не найдена ни в одной карте", "error")

    return deleted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage CIDR assignments for Kubernetes nodes")

    parser.add_argument("--action", choices=["register", "delete"], required=True,
                        help="Action to perform: register or delete")

    parser.add_argument("--cpb", action="store_true",
                        help="Use collected_info.py to get node parameters")
    parser.add_argument("--name", help="Node hostname")
    parser.add_argument("--ip", help="Node global IP")
    parser.add_argument("--role", choices=["control-plane", "worker"], help="Node role")

    args = parser.parse_args()

    if args.action == "register":
        if args.cpb:
            name, ip, role, cluster_cidr = extract_info_from_py()
        else:
            if not (args.name and args.ip and args.role):
                parser.error("Must provide --name, --ip and --role for register unless using --cpb")
            name, ip, role = args.name, args.ip, args.role

        result = assign_cidr(role, name, ip)
        print(json.dumps(result, indent=4))

    elif args.action == "delete":
        if not args.name:
            parser.error("Must provide --name for delete")
        delete_node_entry(args.name)