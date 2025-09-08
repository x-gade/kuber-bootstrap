#!/usr/bin/env python3
"""
Script for joining a worker node to Kubernetes cluster.
Скрипт для присоединения рабочей ноды к Kubernetes-кластеру.
"""

import subprocess
import re
import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log

JOIN_INFO_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "join_info.json")


def ask_input(prompt: str, pattern: str, error_text: str) -> str:
    """
    Prompt user input with validation via regex.
    Запрашивает ввод у пользователя и проверяет через регулярку.
    """
    while True:
        user_input = input(prompt).strip()
        if re.fullmatch(pattern, user_input):
            return user_input
        log(error_text, "warn")


def load_join_info():
    """
    Load join parameters from data/join_info.json if it exists.
    Загружает параметры join из data/join_info.json, если он существует.
    """
    if not os.path.exists(JOIN_INFO_PATH):
        log("join_info.json не найден, переключаюсь на ручной ввод", "warn")
        return None

    try:
        with open(JOIN_INFO_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Проверяем, что ключи есть
        if all(k in data for k in ("CONTROL_PLANE_IP", "JOIN_TOKEN", "DISCOVERY_HASH")):
            log("Параметры join загружены из join_info.json", "ok")
            return data
        else:
            log("join_info.json неполный, требуется ручной ввод", "warn")
            return None
    except Exception as e:
        log(f"Ошибка чтения join_info.json: {e}", "error")
        return None


def run_kubeadm_join(ip: str, token: str, discovery_hash: str):
    """
    Run kubeadm join with provided parameters.
    Выполняет kubeadm join с переданными параметрами.
    """
    join_cmd = [
        "kubeadm", "join",
        f"{ip}:6443",
        "--token", token,
        "--discovery-token-ca-cert-hash", discovery_hash
    ]

    log(f"Выполняется команда: {' '.join(join_cmd)}", "info")
    try:
        subprocess.run(join_cmd, check=True)
        log("Успешное присоединение к кластеру", "ok")
    except subprocess.CalledProcessError as e:
        log(f"Ошибка при выполнении kubeadm join: {e}", "error")
        sys.exit(1)


def main():
    log("Присоединение к кластеру Kubernetes", "info")

    join_info = load_join_info()

    if join_info:
        ip = join_info["CONTROL_PLANE_IP"]
        token = join_info["JOIN_TOKEN"]
        discovery_hash = join_info["DISCOVERY_HASH"]
    else:
        # Ручной ввод
        ip = ask_input(
            "Введите IP главного control-plane узла: ",
            r"\d{1,3}(\.\d{1,3}){3}",
            "Некорректный формат IP"
        )
        token = ask_input(
            "Введите токен kubeadm: ",
            r"[a-z0-9]{6}\.[a-z0-9]{16}",
            "Некорректный формат токена (ожидается <abcdef>.<0123456789abcdef>)"
        )
        discovery_hash = ask_input(
            "Введите discovery-token-ca-cert-hash (начиная с sha256:): ",
            r"sha256:[a-f0-9]{64}",
            "Некорректный формат discovery hash"
        )

    run_kubeadm_join(ip, token, discovery_hash)


if __name__ == "__main__":
    main()
