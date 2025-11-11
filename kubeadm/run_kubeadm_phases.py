#!/usr/bin/env python3
"""
Run preparation steps for kubeadm phases on control-plane.
Выполняет подготовительные шаги для фаз kubeadm на управляющем узле.
"""

import os
import subprocess
import time
import sys

# Добавление корня проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data.collected_info import ROLE, HOSTNAME

# Пути к kubeconfig и флагам kubelet
KUBECONFIG_PATH = "/etc/kubernetes/admin.conf"
KUBELET_FLAGS_ENV = "/var/lib/kubelet/kubeadm-flags.env"

def run(cmd, error_msg="Ошибка выполнения команды"):
    """
    Run a shell command and handle error logging.
    Выполняет команду и логирует ошибку при неудаче.
    """
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        log(f"{error_msg}: {e}", "error")
        return False

def start_kubelet():
    """
    Remove default kubeadm flags and start kubelet using systemd configuration.
    Удаляет старые флаги kubeadm и запускает kubelet через systemd-настройки.
    """
    log("[PHASE] Конфигурация и запуск kubelet", "step")
    if os.path.exists(KUBELET_FLAGS_ENV):
        os.remove(KUBELET_FLAGS_ENV)
        log("Удалён kubeadm-flags.env — теперь только systemd управляет параметрами kubelet", "warn")

    # Генерация конфигурации флагов для systemd и запуск
    subprocess.run(["python3", "kubelet/manage_kubelet_config.py", "--mode", "flags"], check=True)

def wait_for_apiserver():
    """
    Wait for kube-apiserver to respond on /healthz endpoint.
    Ожидает доступности kube-apiserver по адресу /healthz.
    """
    log("Ожидание ответа от kube-apiserver (/healthz)...", "info")
    for _ in range(30):  # максимум 90 секунд
        try:
            out = subprocess.check_output([
                "curl", "-sf", "--max-time", "2",
                "https://127.0.0.1:6443/healthz", "--insecure"
            ])
            if b"ok" in out:
                log("kube-apiserver доступен", "ok")
                return True
        except subprocess.CalledProcessError:
            pass
        time.sleep(3)
    log("kube-apiserver не ответил за 90 секунд", "error")
    return False

def main():
    """
    Entry point: prepare control-plane for further kubeadm phases.
    Точка входа: подготавливает управляющий узел к дальнейшим фазам kubeadm.
    """
    if ROLE != "control-plane":
        log("Пропуск инициализации: текущая нода не является control-plane", "warn")
        return

    os.environ.setdefault("KUBECONFIG", KUBECONFIG_PATH)

    start_kubelet()

    if not wait_for_apiserver():
        sys.exit(1)

    log("kubelet и apiserver запущены. Инициализация продолжится после установки CNI", "ok")

if __name__ == "__main__":
    main()