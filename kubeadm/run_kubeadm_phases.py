# kubeadm/run_kubeadm_phases.py

import os
import subprocess
import time
import sys
import socket

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data.collected_info import ROLE, HOSTNAME

KUBELET_CONF = "/etc/kubernetes/kubelet.conf"
KUBELET_UNIT_FILE = "/etc/systemd/system/kubelet.service.d/10-kubeadm.conf"
KUBELET_FLAGS_ENV = "/var/lib/kubelet/kubeadm-flags.env"

# Получаем IP-адрес текущей машины (для node-ip)
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

SYSTEMD_KUBELET_CONF = f"""[Service]
Environment="KUBELET_KUBECONFIG_ARGS=--kubeconfig={KUBELET_CONF}"
Environment="KUBELET_CONFIG_ARGS=--config=/var/lib/kubelet/config.yaml --container-runtime-endpoint=unix:///var/run/containerd/containerd.sock --pod-infra-container-image=registry.k8s.io/pause:3.9 --node-ip={get_ip()} --pod-cidr=10.244.0.0/16"
ExecStart=
ExecStart=/usr/bin/kubelet $KUBELET_KUBECONFIG_ARGS $KUBELET_CONFIG_ARGS
"""

def run(cmd, error_msg="Ошибка выполнения команды"):
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        log(f"{error_msg}: {e}", "error")
        return False

def start_kubelet():
    log("[PHASE] Запуск kubelet", "step")
    if os.path.exists(KUBELET_FLAGS_ENV):
        os.remove(KUBELET_FLAGS_ENV)
        log("Удалён kubeadm-flags.env — теперь только systemd управляет параметрами kubelet", "warn")

    os.makedirs(os.path.dirname(KUBELET_UNIT_FILE), exist_ok=True)
    with open(KUBELET_UNIT_FILE, "w") as f:
        f.write(SYSTEMD_KUBELET_CONF)
        log("Файл 10-kubeadm.conf успешно перезаписан с необходимыми параметрами", "ok")

    run(["systemctl", "daemon-reexec"])
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "kubelet"])
    run(["systemctl", "restart", "kubelet"])
    log("kubelet перезапущен", "ok")

def wait_for_apiserver():
    log("Ожидание доступности kube-apiserver через kubectl...", "info")
    for i in range(30):
        try:
            subprocess.check_output(["kubectl", "get", "--raw", "/healthz"])
            log("kube-apiserver доступен", "ok")
            return True
        except subprocess.CalledProcessError:
            pass
        time.sleep(3)
    log("kube-apiserver не ответил за 90 секунд", "error")
    return False

def create_cluster_rolebinding():
    log("[PHASE] Назначение прав cluster-admin пользователю kubernetes-admin", "step")
    return run([
        "kubectl", "create", "clusterrolebinding", "root-cluster-admin-binding",
        "--clusterrole=cluster-admin",
        "--user=kubernetes-admin"
    ], "Не удалось создать clusterrolebinding")

# Отключено временно до установки CNI, иначе нода не появится
def wait_for_node_registration():
    log("Ожидание регистрации текущей ноды в Kubernetes...", "info")
    for i in range(30):
        try:
            out = subprocess.check_output(["kubectl", "get", "node", HOSTNAME])
            if HOSTNAME in out.decode():
                log(f"Нода {HOSTNAME} успешно зарегистрирована", "ok")
                return True
        except subprocess.CalledProcessError:
            pass
        time.sleep(3)
    log(f"Нода {HOSTNAME} не зарегистрирована за 90 секунд", "error")
    return False

def main():
    if ROLE != "control-plane":
        log("Пропуск инициализации: текущая нода не является control-plane", "warn")
        return

    start_kubelet()

    if not wait_for_apiserver():
        sys.exit(1)

    if not create_cluster_rolebinding():
        sys.exit(1)

    log("⚠️ Регистрация ноды будет происходить после установки CNI", "warn")
    # if not wait_for_node_registration():
    #     sys.exit(1)

    log("Ручная инициализация control-plane завершена успешно", "ok")

if __name__ == "__main__":
    main()
