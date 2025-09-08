#!/usr/bin/env python3
"""
Node Intake Client
Одноразовый клиент для взаимодействия с FastAPI-сервисом cps_service.py

Функционал:
 - register: регистрирует новую ноду в кластере (отправляет hostname, ip, role)
 - delete: удаляет ноду из кластера и IPAM

Пример использования:
    python3 node_intake_client.py register --host 127.0.0.1 --hostname omen179046 --ip 192.168.0.1 --role worker --token rizilz.ro3nxrm4ap8xryo3
    python3 node_intake_client.py delete --host 127.0.0.1 --hostname omen179046 --role worker --token rizilz.ro3nxrm4ap8xryo3
"""

import os
import sys
import json
import argparse
import requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from utils.logger import log  # централизованный логгер


def register_node(server_host: str, hostname: str, node_ip: str, role: str, token: str, port: int = 5050):
    """
    Send /register request to intake server.
    Отправляет запрос на регистрацию ноды на intake сервер.
    """
    url = f"http://{server_host}:{port}/register"

    payload = {
        "node": {
            "hostname": hostname,
            "ip": node_ip,
            "role": role
        },
        "token": token
    }

    log(f"Отправка запроса на регистрацию {hostname} ({role}, {node_ip}) -> {url}", "info")

    try:
        resp = requests.post(url, json=payload, timeout=15)
    except requests.exceptions.RequestException as e:
        log(f"Ошибка подключения к серверу {url}: {e}", "error")
        sys.exit(1)

    if resp.status_code == 200:
        try:
            data = resp.json()
            log(f"Успешная регистрация. CIDR: {data.get('cidr', '?')}", "ok")
            print(json.dumps(data, indent=2))
        except json.JSONDecodeError:
            log("Сервер вернул некорректный JSON", "error")
            print(resp.text)
            sys.exit(1)
    else:
        log(f"Ошибка регистрации ({resp.status_code}): {resp.text}", "error")
        sys.exit(1)


def delete_node(server_host: str, hostname: str, role: str, token: str, port: int = 5050):
    """
    Send /delete request to intake server.
    Отправляет запрос на удаление ноды с intake сервера.
    """
    url = f"http://{server_host}:{port}/delete"

    payload = {
        "node": {
            "hostname": hostname,
            "role": role
        },
        "token": token
    }

    log(f"Отправка запроса на удаление {hostname} ({role}) -> {url}", "warn")

    try:
        resp = requests.post(url, json=payload, timeout=15)
    except requests.exceptions.RequestException as e:
        log(f"Ошибка подключения к серверу {url}: {e}", "error")
        sys.exit(1)

    if resp.status_code == 200:
        try:
            data = resp.json()
            log(f"Успешное удаление {hostname}", "ok")
            print(json.dumps(data, indent=2))
        except json.JSONDecodeError:
            log("Сервер вернул некорректный JSON", "error")
            print(resp.text)
            sys.exit(1)
    else:
        log(f"Ошибка удаления ({resp.status_code}): {resp.text}", "error")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Node Intake Client")
    subparsers = parser.add_subparsers(dest="action", help="Action: register or delete")

    # === register ===
    reg_parser = subparsers.add_parser("register", help="Register new node")
    reg_parser.add_argument("--host", required=True, help="Intake server host/IP")
    reg_parser.add_argument("--hostname", required=True, help="Node hostname")
    reg_parser.add_argument("--ip", required=True, help="Node global IP")
    reg_parser.add_argument("--role", required=True, choices=["worker", "control-plane"], help="Node role")
    reg_parser.add_argument("--token", required=True, help="JOIN_TOKEN for auth")
    reg_parser.add_argument("--port", default=5050, type=int, help="Server port (default 5050)")

    # === delete ===
    del_parser = subparsers.add_parser("delete", help="Delete node")
    del_parser.add_argument("--host", required=True, help="Intake server host/IP")
    del_parser.add_argument("--hostname", required=True, help="Node hostname")
    del_parser.add_argument("--role", required=True, choices=["worker", "control-plane"], help="Node role")
    del_parser.add_argument("--token", required=True, help="JOIN_TOKEN for auth")
    del_parser.add_argument("--port", default=5050, type=int, help="Server port (default 5050)")

    args = parser.parse_args()

    if args.action == "register":
        register_node(args.host, args.hostname, args.ip, args.role, args.token, args.port)
    elif args.action == "delete":
        delete_node(args.host, args.hostname, args.role, args.token, args.port)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
