#!/usr/bin/env python3
"""
Control-plane Intake + IPAM Service
Интеграционный сервис Intake + IPAM на control-plane

Этот сервис запускается на control-plane узле Kubernetes и предоставляет HTTP API для:
 - регистрации новых worker/control-plane нод,
 - вызова mapper.py для выдачи или очистки CIDR,
 - назначения ролей нодам через kubectl label,
 - удаления нод из кластера и IPAM карт.
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
import uvicorn

# === Добавляем корень проекта для логгера ===
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from utils.logger import log  # централизованный логгер

# === Константы ===
API_HOST = "127.0.0.1"
API_PORT = 5050
COLLECTED_INFO_PATH = PROJECT_ROOT / "data" / "collected_info.py"
MAPPER_PATH = PROJECT_ROOT / "cluster" / "ipam_cilium" / "mapper.py"

# Явно указываем kubeconfig для всех kubectl-команд
KUBECONFIG_PATH = "/etc/kubernetes/admin.conf"

app = FastAPI(title="Kubernetes Intake + IPAM Service", version="0.2.1")


def load_join_token() -> str:
    """
    Load JOIN_TOKEN from collected_info.py
    Загружает JOIN_TOKEN из collected_info.py
    """
    namespace = {}
    if not COLLECTED_INFO_PATH.exists():
        log(f"Файл collected_info.py не найден: {COLLECTED_INFO_PATH}", "error")
        raise FileNotFoundError("Missing collected_info.py")
    exec(COLLECTED_INFO_PATH.read_text(), namespace)
    token = namespace.get("JOIN_TOKEN")
    if not token:
        raise ValueError("JOIN_TOKEN not found in collected_info.py")
    return token


def kubectl_label_node(hostname: str, role: str) -> bool:
    """
    Label Kubernetes node with a specific role
    Назначает ноде Kubernetes роль через kubectl label
    """
    label_key = f"node-role.kubernetes.io/{role}"
    cmd = [
        "kubectl", "--kubeconfig", KUBECONFIG_PATH,
        "label", "node", hostname,
        f"{label_key}=true", "--overwrite"
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode == 0:
        log(f"Нода {hostname} успешно промаркирована ролью {role}", "ok")
        return True
    else:
        log(f"Ошибка при назначении роли {role} ноде {hostname}: {result.stderr.decode()}", "error")
        return False


def kubectl_delete_node(hostname: str) -> bool:
    """
    Delete node from Kubernetes cluster
    Удаляет ноду из кластера Kubernetes
    """
    cmd = ["kubectl", "--kubeconfig", KUBECONFIG_PATH, "delete", "node", hostname]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode == 0:
        log(f"Нода {hostname} удалена из кластера", "ok")
        return True
    else:
        log(f"Ошибка при удалении ноды {hostname}: {result.stderr.decode()}", "error")
        return False


def run_mapper(action: str, hostname: str, role: str = None, ip: str = None) -> dict:
    cmd = [sys.executable, str(MAPPER_PATH), "--action", action]

    if action == "register":
        cmd += ["--name", hostname, "--ip", ip, "--role", role]
    elif action == "delete":
        cmd += ["--name", hostname]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        log(f"Ошибка mapper.py ({action}): {result.stderr.strip()}", "error")
        raise HTTPException(status_code=500, detail=result.stderr.strip())

    stdout = result.stdout.strip()

    # Находим JSON-блок внутри stdout
    json_start = stdout.find("{")
    json_end = stdout.rfind("}") + 1
    if json_start != -1 and json_end > json_start:
        try:
            json_part = stdout[json_start:json_end]
            return json.loads(json_part)
        except json.JSONDecodeError:
            log(f"Не удалось распарсить JSON-часть: {json_part}", "error")

    # Если не нашли JSON, возвращаем сырое
    log(f"mapper.py вернул не-JSON: {stdout}", "warn")
    return {"raw": stdout}


@app.post("/register")
async def register_node(request: Request):
    """
    Register a new node and assign a CIDR block.
    Регистрирует новую ноду через mapper.py и выдает CIDR.

    Request JSON:
    {
      "node": {
        "hostname": "omen179046",
        "ip": "192.168.0.1",
        "role": "worker"
      },
      "token": "rizilz.ro3nxrm4ap8xryo3"
    }

    Response JSON:
    {
      "role": "worker",
      "name": "omen179046",
      "globalip": "192.168.0.1",
      "cidr": "10.244.2.0/24",
      "clasterip": "10.244.2.0"
    }
    """
    data = await request.json()

    # === Проверка токена ===
    token = data.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Missing token")

    valid_token = load_join_token()
    if token != valid_token:
        log(f"Ошибка авторизации: неверный токен {token}", "error")
        raise HTTPException(status_code=401, detail="Invalid token")

    node_info = data.get("node")
    if not node_info:
        raise HTTPException(status_code=400, detail="Missing node info")

    hostname = node_info.get("hostname")
    global_ip = node_info.get("ip")
    role = node_info.get("role")

    if not (hostname and global_ip and role):
        raise HTTPException(status_code=400, detail="Incomplete node info")

    log(f"Запрос на регистрацию ноды: {hostname} ({role}, {global_ip})", "info")

    # === Вызов mapper.py register ===
    cidr_entry = run_mapper("register", hostname, role, global_ip)

    # === Промаркировать ноду ===
    if not kubectl_label_node(hostname, role):
        raise HTTPException(status_code=500, detail="Failed to label node")

    log(f"Нода {hostname} зарегистрирована и получила CIDR {cidr_entry.get('cidr', '?')}", "ok")

    return cidr_entry


@app.post("/delete")
async def delete_node(request: Request):
    """
    Delete a node from cluster and cleanup IPAM map.
    Удаляет ноду из кластера и IPAM карты через mapper.py

    Request JSON:
    {
      "node": {
        "hostname": "worker_node",
        "role": "worker"
      },
      "token": "qwerty.asdfghjklzxcvbn"
    }

    Response JSON:
    {
      "status": "ok"
    }
    """
    data = await request.json()

    # === Проверка токена ===
    token = data.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Missing token")

    valid_token = load_join_token()
    if token != valid_token:
        log(f"Ошибка авторизации: неверный токен {token}", "error")
        raise HTTPException(status_code=401, detail="Invalid token")

    node_info = data.get("node")
    if not node_info:
        raise HTTPException(status_code=400, detail="Missing node info")

    hostname = node_info.get("hostname")
    if not hostname:
        raise HTTPException(status_code=400, detail="Missing hostname")

    log(f"Запрос на удаление ноды: {hostname}", "warn")

    # === Удаляем ноду из кластера ===
    if not kubectl_delete_node(hostname):
        raise HTTPException(status_code=500, detail="Failed to delete node from cluster")

    # === Вызов mapper.py delete ===
    mapper_response = run_mapper("delete", hostname)

    log(f"Нода {hostname} удалена и очищена в IPAM", "ok")

    return mapper_response


def run_server():
    """
    Run FastAPI server for control-plane intake
    Запускает FastAPI сервер intake на control-plane
    """
    log(f"Запуск Intake + IPAM сервиса на {API_HOST}:{API_PORT}", "info")
    uvicorn.run(app, host=API_HOST, port=API_PORT)


if __name__ == "__main__":
    run_server()
