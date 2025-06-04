#!/usr/bin/env python3

import subprocess
import sys
import os
import json

# Добавляем путь к модулям
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from data import collected_info
from utils.logger import log


def get_current_labels(node_name: str) -> dict:
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
    node_name = collected_info.HOSTNAME
    role = collected_info.ROLE

    log(f"Назначение роли '{role}' ноде '{node_name}'", "info")
    label_node(node_name, role)


if __name__ == "__main__":
    main()
