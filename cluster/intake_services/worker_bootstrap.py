#!/usr/bin/env python3
"""
Worker Bootstrap Script
Подключается к control-plane по SSH, регистрирует воркер-ноду через register
и сохраняет полученный JSON в cluster/ipam_cilium/maps/worker_map.json
"""

import sys
import json
import subprocess
import re
from pathlib import Path

# === Пути ===
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CLUSTER_MAPS_DIR = PROJECT_ROOT / "cluster" / "ipam_cilium" / "maps"
WORKER_MAP_FILE = CLUSTER_MAPS_DIR / "worker_map.json"
SSH_KEY_PATH = Path.home() / ".ssh" / "ipam-client.key"

# Добавляем корень проекта в sys.path для импорта логгера
sys.path.insert(0, str(PROJECT_ROOT))
from utils.logger import log

# === Константы ===
SSH_PORT = "3333"
REMOTE_USER = "ipam-client"


def load_collected_info():
    """
    Load local node metadata from collected_info.py
    Загружает информацию о текущей ноде из collected_info.py
    """
    collected_file = DATA_DIR / "collected_info.py"
    if not collected_file.exists():
        log("Файл collected_info.py не найден! Запустите collect_node_info.py", "error")
        sys.exit(1)

    namespace = {}
    exec(collected_file.read_text(), namespace)

    required = ["HOSTNAME", "IP", "ROLE"]
    for r in required:
        if r not in namespace:
            log(f"Не найден параметр {r} в collected_info.py", "error")
            sys.exit(1)

    return {
        "hostname": namespace["HOSTNAME"],
        "ip": namespace["IP"],
        "role": namespace["ROLE"]
    }


def load_join_info():
    """
    Load control-plane IP and token from join_info.json
    Загружает IP и токен из файла join_info.json для подключения к control-plane
    """
    join_file = DATA_DIR / "join_info.json"
    if not join_file.exists():
        log("Файл join_info.json не найден! Скопируйте его с control-plane", "error")
        sys.exit(1)

    with open(join_file, "r", encoding="utf-8") as f:
        join_data = json.load(f)

    required = ["CONTROL_PLANE_IP", "JOIN_TOKEN"]
    for r in required:
        if r not in join_data:
            log(f"Не найден параметр {r} в join_info.json", "error")
            sys.exit(1)

    return {
        "control_plane_ip": join_data["CONTROL_PLANE_IP"],
        "token": join_data["JOIN_TOKEN"]
    }


def ssh_register_node(control_plane_ip, node_info, token):
    """
    SSH into control-plane and register the worker node
    Подключается по SSH к control-plane и регистрирует ноду через CLI `register`
    """
    hostname = node_info["hostname"]
    node_ip = node_info["ip"]
    role = node_info["role"]

    remote_cmd = (
        f"register "
        f"--host 127.0.0.1 "
        f"--hostname {hostname} "
        f"--ip {node_ip} "
        f"--role {role} "
        f"--token {token}"
    )

    ssh_cmd = [
        "ssh",
        "-i", str(SSH_KEY_PATH),
        "-p", SSH_PORT,
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        f"{REMOTE_USER}@{control_plane_ip}",
        remote_cmd
    ]

    log(f"Подключение к control-plane {control_plane_ip}:{SSH_PORT} и регистрация ноды...", "info")

    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, check=True)
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if stderr:
            log(f"STDERR: {stderr}", "warn")

        json_match = re.search(r"\{.*\}", stdout, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            log(f"Регистрация успешна. CIDR: {data.get('cidr', '?')}", "ok")
            return data
        else:
            log("Ответ сервера не содержит корректного JSON", "error")
            print(stdout)
            sys.exit(1)

    except subprocess.CalledProcessError as e:
        log(f"Ошибка SSH подключения: {e}", "error")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        sys.exit(1)


def save_worker_map(data):
    """
    Save received IPAM map to worker_map.json
    Сохраняет полученную IPAM-карту в файл worker_map.json
    """
    CLUSTER_MAPS_DIR.mkdir(parents=True, exist_ok=True)
    with open(WORKER_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    log(f"Ответ сервера сохранён в {WORKER_MAP_FILE}", "ok")


def main():
    """
    Entry point: perform worker bootstrap
    Точка входа: выполняет bootstrap текущей воркер-ноды
    """
    log("Bootstrap воркер-ноды...", "info")

    node_info = load_collected_info()
    if node_info["role"] != "worker":
        log(f"Роль ноды не worker (ROLE={node_info['role']}). Прерывание.", "error")
        sys.exit(1)

    join_info = load_join_info()

    subprocess.run(["ssh-keygen", "-R", f"[{join_info['control_plane_ip']}]:{SSH_PORT}"], stdout=subprocess.DEVNULL)

    result_json = ssh_register_node(
        join_info["control_plane_ip"],
        node_info,
        join_info["token"]
    )

    save_worker_map(result_json)


if __name__ == "__main__":
    main()
