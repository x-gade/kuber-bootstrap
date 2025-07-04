#!/usr/bin/env python3
"""
Entry point for initializing IPAM Cilium addressing system
during Kubernetes installation.

Точка входа для инициализации системы адресации IPAM Cilium
во время установки Kubernetes.
"""

import os
import subprocess
import sys
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from utils.logger import log

# Шаги для control-plane bootstrap
CPB_STEPS = [
    ("Формирование карты адресов", "mapper.py --cpb"),
    ("Применение параметров к CiliumNode", "patcher.py --cpb")
]

# Шаги для подключения второго/последующих control-plane узлов
CP_STEPS = [
    ("[Заглушка] Проверка состояния кластера", "echo 'Control-plane подключение: шаг пока не реализован'")
]

# Шаги для подключения worker-ноды
W_STEPS = [
    ("[Заглушка] Получение адреса из центра", "echo 'Worker-нода подключение: шаг пока не реализован'")
]

def run_script(title, command):
    """
    Run a script and log its output.
    Запускает скрипт и логирует его вывод.
    """
    log(f"==> {title} [{command}]", "step")
    try:
        parts = command.split()
        first = parts[0]

        # Определяем абсолютный путь для локальных .py, иначе оставляем как есть (например, echo)
        if first.endswith(".py"):
            script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), first))
            if not os.path.exists(script_path):
                raise FileNotFoundError(f"Файл не найден: {script_path}")
            result = subprocess.run(["python3", script_path] + parts[1:], stdout=sys.stdout, stderr=sys.stderr)
        else:
            result = subprocess.run(parts, stdout=sys.stdout, stderr=sys.stderr)

        if result.returncode != 0:
            log(f"Ошибка в шаге {title}", "error")
            sys.exit(1)

        log(f"Завершено: {title}", "ok")

    except Exception as e:
        log(f"Ошибка при выполнении: {title} — {e}", "error")
        sys.exit(1)

def run_pipeline(label: str, steps: list):
    """
    Execute a list of (name, command) steps.
    Выполняет последовательность шагов пайплайна.
    """
    log(f"[IPAM] Запуск пайплайна инициализации: {label}", "info")
    for step_name, script_command in steps:
        run_script(step_name, script_command)
    log(f"[IPAM] Завершение этапа: {label}", "ok")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IPAM init entrypoint")
    parser.add_argument("--cpb", action="store_true", help="Control-plane bootstrap")
    parser.add_argument("--cp", action="store_true", help="Secondary control-plane node")
    parser.add_argument("--w", action="store_true", help="Worker node")

    args = parser.parse_args()

    if args.cpb:
        run_pipeline("Control-plane bootstrap", CPB_STEPS)
    elif args.cp:
        run_pipeline("Control-plane node", CP_STEPS)
    elif args.w:
        run_pipeline("Worker node", W_STEPS)
    else:
        log("Не передан ни один из флагов: --cpb / --cp / --w", "error")
        sys.exit(1)
