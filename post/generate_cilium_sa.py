#!/usr/bin/env python3
"""
Ensure Cilium service account and kubeconfig token
Автоматически проверяет наличие сервис-аккаунта Cilium, создает его, права, токен и сохраняет.
"""

import subprocess
import os
import sys
from pathlib import Path

# Подключаем логгер
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from utils.logger import log

# Пути и переменные
COLLECTED_INFO_PATH = "/opt/kuber-bootstrap/data/collected_info.py"
NAMESPACE = "kube-system"
SERVICE_ACCOUNT = "cilium"
CLUSTER_ROLE_BINDING = "cilium-binding"


def run_cmd(cmd: list, capture=True):
    """Run a shell command and return output"""
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
    """Проверяем наличие сервис-аккаунта Cilium, если нет - создаем"""
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
    """Проверяем наличие ClusterRoleBinding, если нет - создаем"""
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
    """Генерируем новый токен для Cilium ServiceAccount"""
    log(f"Создаем новый токен для ServiceAccount '{SERVICE_ACCOUNT}'...", "info")
    token = run_cmd(["kubectl", "create", "token", SERVICE_ACCOUNT, "-n", NAMESPACE, "--duration=8760h"])
    if token:
        log("Токен успешно получен", "ok")
        return token
    log("Не удалось получить токен", "error")
    return None


def save_token_to_collected_info(token: str):
    """Сохраняем токен в data/collected_info.py"""
    log("Сохраняем токен в collected_info.py...", "info")

    path = Path(COLLECTED_INFO_PATH)
    if not path.exists():
        log("Файл collected_info.py не найден, создаём новый...", "warn")
        path.write_text("# collected cluster info\n")

    # Читаем файл
    content = path.read_text().splitlines()

    # Удаляем старую строку с CILIUM_TOKEN если есть
    content = [line for line in content if not line.strip().startswith("CILIUM_TOKEN")]

    # Добавляем новый токен
    content.append(f'CILIUM_TOKEN = "{token}"')

    # Записываем обратно
    path.write_text("\n".join(content) + "\n")
    log("Токен успешно записан в collected_info.py", "ok")


def main():
    log("=== Инициализация Cilium ServiceAccount ===", "info")

    # Проверяем/создаем SA и Binding
    if not ensure_service_account():
        sys.exit(1)
    if not ensure_clusterrolebinding():
        sys.exit(1)

    # Генерируем токен
    token = generate_token()
    if not token:
        sys.exit(1)

    # Сохраняем токен
    save_token_to_collected_info(token)

    # Переменная доступна для других скриптов
    log(f"Cilium Token: {token}", "ok")
    log("Cilium ServiceAccount готов!", "ok")


if __name__ == "__main__":
    main()
