# kubeadm/generate_kubelet_kubeconfig.py

import subprocess
import os
import sys

# Подключаем utils/ для импорта логгера
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log

KUBECONFIG_PATH = "/etc/kubernetes/kubelet.conf"

def run_cmd(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"Команда завершилась с ошибкой: {' '.join(cmd)}", "error")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)

def generate_kubelet_kubeconfig():
    log("Генерация kubelet kubeconfig...", "step")

    os.makedirs("/etc/kubernetes", exist_ok=True)

    run_cmd([
        "kubectl", "config", "set-cluster", "default-cluster",
        "--certificate-authority=/etc/kubernetes/pki/ca.crt",
        "--server=https://127.0.0.1:6443",
        f"--kubeconfig={KUBECONFIG_PATH}"
    ])

    run_cmd([
        "kubectl", "config", "set-credentials", "default-node",
        "--client-certificate=/etc/kubernetes/pki/kubelet-client.crt",
        "--client-key=/etc/kubernetes/pki/kubelet-client.key",
        f"--kubeconfig={KUBECONFIG_PATH}"
    ])

    run_cmd([
        "kubectl", "config", "set-context", "default",
        "--cluster=default-cluster",
        "--user=default-node",
        f"--kubeconfig={KUBECONFIG_PATH}"
    ])

    run_cmd([
        "kubectl", "config", "use-context", "default",
        f"--kubeconfig={KUBECONFIG_PATH}"
    ])

    log(f"Kubelet kubeconfig создан: {KUBECONFIG_PATH}", "ok")

if __name__ == "__main__":
    generate_kubelet_kubeconfig()
