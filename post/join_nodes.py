"""
Script for joining a worker node to Kubernetes cluster.
Скрипт для присоединения рабочей ноды к Kubernetes-кластеру.
"""

import subprocess
import re
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log


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


def main():
    log("Присоединение к кластеру Kubernetes", "info")

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

    join_cmd = [
        "kubeadm", "join",
        f"{ip}:6443",
        "--token", token,
        "--discovery-token-ca-cert-hash", discovery_hash
    ]

    log("Выполняется команда kubeadm join...", "info")
    try:
        subprocess.run(join_cmd, check=True)
        log("Успешное присоединение к кластеру", "ok")
    except subprocess.CalledProcessError as e:
        log(f"Ошибка при выполнении kubeadm join: {e}", "error")
        sys.exit(1)


if __name__ == "__main__":
    main()
