#!/usr/bin/env python3
"""
Ensure Cilium service account and kubeconfig token
Автоматически проверяет наличие сервис-аккаунта Cilium, создает его, права, токен и сохраняет.
"""

import subprocess
import os
import sys
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from utils.logger import log

COLLECTED_INFO_PATH = "/opt/kuber-bootstrap/data/collected_info.py"
NAMESPACE = "kube-system"
SERVICE_ACCOUNT = "cilium"
CLUSTER_ROLE_BINDING = "cilium-binding"


def run_cmd(cmd: list, capture=True):
    """
    Run a shell command and return output if requested
    Выполняет shell-команду и возвращает вывод, если указано

    :param cmd: список аргументов команды
    :param capture: захватывать вывод или нет
    :return: строка с выводом или None при ошибке
    """
    try:
        if capture:
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, check=True)
            return ""
    except subprocess.CalledProcessError as e:
        log(f"Ошибка выполнения команды: {' '.join(cmd)}\n{e.stderr}", "error")
        return None


def ensure_service_account():
    """
    Ensure Cilium ServiceAccount exists or create it
    Проверяет наличие ServiceAccount Cilium и создаёт его при отсутствии

    :return: True при успешной проверке или создании, иначе False
    """
    log(f"Проверяем наличие ServiceAccount '{SERVICE_ACCOUNT}' в {NAMESPACE}...", "info")
    sa_list = run_cmd(["kubectl", "get", "sa", "-n", NAMESPACE])
    if sa_list and SERVICE_ACCOUNT in sa_list:
        log(f"ServiceAccount '{SERVICE_ACCOUNT}' уже существует", "ok")
        return True

    log(f"Создаем ServiceAccount '{SERVICE_ACCOUNT}'...", "info")
    result = run_cmd(["kubectl", "create", "serviceaccount", SERVICE_ACCOUNT, "-n", NAMESPACE])
    if result:
        log(result, "ok")
        return True
    return False


def ensure_clusterrolebinding():
    """
    Ensure ClusterRoleBinding for Cilium exists or create it
    Проверяет наличие ClusterRoleBinding и создаёт его при отсутствии

    :return: True при успешной проверке или создании, иначе False
    """
    log(f"Проверяем наличие ClusterRoleBinding '{CLUSTER_ROLE_BINDING}'...", "info")
    crb_list = run_cmd(["kubectl", "get", "clusterrolebinding"])
    if crb_list and CLUSTER_ROLE_BINDING in crb_list:
        log(f"ClusterRoleBinding '{CLUSTER_ROLE_BINDING}' уже существует", "ok")
        return True

    log(f"Создаем ClusterRoleBinding '{CLUSTER_ROLE_BINDING}'...", "info")
    result = run_cmd([
        "kubectl", "create", "clusterrolebinding", CLUSTER_ROLE_BINDING,
        "--clusterrole=cluster-admin",
        f"--serviceaccount={NAMESPACE}:{SERVICE_ACCOUNT}"
    ])
    if result:
        log(result, "ok")
        return True
    return False


def generate_token():
    """
    Generate a long-lived token for the Cilium ServiceAccount
    Генерирует долговременный токен для ServiceAccount Cilium

    :return: строка с токеном или None при ошибке
    """
    log(f"Создаем новый токен для ServiceAccount '{SERVICE_ACCOUNT}'...", "info")
    token = run_cmd(["kubectl", "create", "token", SERVICE_ACCOUNT, "-n", NAMESPACE, "--duration=8760h"])
    if token:
        log("Токен успешно получен", "ok")
        return token
    log("Не удалось получить токен", "error")
    return None


def save_token_to_collected_info(token: str):
    """
    Save generated token into collected_info.py file
    Сохраняет сгенерированный токен в файл collected_info.py

    :param token: строка токена для сохранения
    """
    log("Сохраняем токен в collected_info.py...", "info")

    path = Path(COLLECTED_INFO_PATH)
    if not path.exists():
        log("Файл collected_info.py не найден, создаём новый...", "warn")
        path.write_text("# collected cluster info\n")

    content = path.read_text().splitlines()
    content = [line for line in content if not line.strip().startswith("CILIUM_TOKEN")]
    content.append(f'CILIUM_TOKEN = "{token}"')

    path.write_text("\n".join(content) + "\n")
    log("Токен успешно записан в collected_info.py", "ok")


def main():
    """
    Main execution flow
    Основной сценарий выполнения:
    - проверка и создание ServiceAccount и RoleBinding
    - генерация токена
    - сохранение токена в collected_info.py
    """
    log("=== Инициализация Cilium ServiceAccount ===", "info")

    if not ensure_service_account():
        sys.exit(1)
    if not ensure_clusterrolebinding():
        sys.exit(1)

    token = generate_token()
    if not token:
        sys.exit(1)

    save_token_to_collected_info(token)

    log(f"Cilium Token: {token}", "ok")
    log("Cilium ServiceAccount готов!", "ok")


if __name__ == "__main__":
    main()
