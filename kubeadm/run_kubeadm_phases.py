# kubeadm/run_kubeadm_phases.py

import os
import subprocess
import time
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data.collected_info import ROLE, HOSTNAME

KUBECONFIG_PATH = "/etc/kubernetes/admin.conf"
KUBELET_FLAGS_ENV = "/var/lib/kubelet/kubeadm-flags.env"


def run(cmd, error_msg="Ошибка выполнения команды"):
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        log(f"{error_msg}: {e}", "error")
        return False


def start_kubelet():
    log("[PHASE] Конфигурация и запуск kubelet", "step")
    if os.path.exists(KUBELET_FLAGS_ENV):
        os.remove(KUBELET_FLAGS_ENV)
        log("Удалён kubeadm-flags.env — теперь только systemd управляет параметрами kubelet", "warn")

    # Применяем шаблонную конфигурацию и перезапускаем
    subprocess.run(["python3", "kubelet/manage_kubelet_config.py", "--mode", "flags"], check=True)


def wait_for_apiserver():
    log("Ожидание ответа от kube-apiserver (/healthz)...", "info")
    for _ in range(30):
        try:
            out = subprocess.check_output(["curl", "-sf", "--max-time", "2", "https://127.0.0.1:6443/healthz", "--insecure"])
            if b"ok" in out:
                log("kube-apiserver доступен", "ok")
                return True
        except subprocess.CalledProcessError:
            pass
        time.sleep(3)
    log("kube-apiserver не ответил за 90 секунд", "error")
    return False


def main():
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
