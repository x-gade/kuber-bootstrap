#!/usr/bin/env python3
"""
Label the Kubernetes node with a role after it joins the cluster.
Добавление метки роли Kubernetes-ноде после подключения к кластеру.
"""

import subprocess
import sys
import os
import json
import time

# Добавляем путь к модулям
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from data import collected_info
from utils.logger import log


def wait_for_node(node_name: str, timeout: int = 60, interval: int = 5) -> bool:
    """
    Wait until the node appears in Kubernetes (up to timeout seconds).
    Ожидание появления ноды в Kubernetes (до timeout секунд).
    """
    log(f"Ожидание появления ноды '{node_name}' в Kubernetes (до {timeout} сек)...", "info")
    elapsed = 0
    while elapsed < timeout:
        result = subprocess.run(
            ["kubectl", "get", "node", node_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            log(f"Нода '{node_name}' обнаружена в Kubernetes", "ok")
            return True
        time.sleep(interval)
        elapsed += interval
    log(f"Нода '{node_name}' не появилась в Kubernetes за {timeout} секунд", "error")
    return False


def get_current_labels(node_name: str) -> dict:
    """
    Retrieve current labels assigned to a node.
    Получает текущие метки, назначенные ноде.
    """
    result = subprocess.run(
        ["kubectl", "get", "node", node_name, "-o", "json"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        log(f"Ошибка при получении меток для {node_name}: {result.stderr}", "error")
        sys.exit(1)

    try:
        data = json.loads(result.stdout)
        return data.get("metadata", {}).get("labels", {})
    except Exception as e:
        log(f"Ошибка при разборе JSON: {e}", "error")
        sys.exit(1)


def label_node(node_name: str, role: str):
    """
    Assign the Kubernetes role label to the specified node.
    Назначает метку роли Kubernetes указанной ноде.
    """
    if not wait_for_node(node_name):
        sys.exit(1)

    label_key = f"node-role.kubernetes.io/{role}"
    label_full = f"{label_key}=true"

    labels = get_current_labels(node_name)
    current_value = labels.get(label_key)

    if current_value == "true":
        log(f"Метка уже установлена: {label_full}", "ok")
        return

    result = subprocess.run(
        ["kubectl", "label", "node", node_name, label_full, "--overwrite"],
        capture_output=True, text=True
    )

    if result.returncode == 0:
        log(f"Метка добавлена или обновлена: {label_full}", "ok")
    else:
        log(f"Не удалось добавить метку: {result.stderr}", "error")
        sys.exit(1)


def main():
    """
    Entry point: assigns the collected role label to the current node.
    Точка входа: назначает собранную роль текущей ноде.
    """
    node_name = collected_info.HOSTNAME
    role = collected_info.ROLE

    log(f"Назначение роли '{role}' ноде '{node_name}'", "info")
    label_node(node_name, role)


if __name__ == "__main__":
    main()