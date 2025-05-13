# setup/install_dependencies.py

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import subprocess
from utils.logger import log

MISSING_FILE = "data/missing_binaries.json"
KUBE_APT_LIST = "/etc/apt/sources.list.d/kubernetes.list"

KUBE_PACKAGES = {"kubelet", "kubeadm", "kubectl"}
EXCLUDED = {"etcd"}  # не устанавливаем — будет создан вручную

def run(cmd):
    log(f"Выполняю: {cmd}", "info")
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        log(f"Ошибка при выполнении: {e}", "error")
        sys.exit(1)

def setup_kubernetes_repo():
    if not os.path.exists(KUBE_APT_LIST):
        log("Добавляю Kubernetes APT-репозиторий", "info")
        run("apt-get update && apt-get install -y apt-transport-https ca-certificates curl")
        run("curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -")
        run('echo "deb https://apt.kubernetes.io/ kubernetes-xenial main" > /etc/apt/sources.list.d/kubernetes.list')
    run("apt-get update")

def install_kube_packages(packages):
    to_install = " ".join(packages)
    run(f"apt-get install -y {to_install}")
    run("apt-mark hold kubelet kubeadm kubectl")

def install_containerd():
    run("apt-get install -y containerd")

def install_missing():
    if not os.path.exists(MISSING_FILE):
        log("Файл missing_binaries.json не найден — пропускаю установку", "warn")
        return

    with open(MISSING_FILE, "r") as f:
        data = json.load(f)

    missing = set(data.get("missing", [])) - EXCLUDED

    if not missing:
        log("Нет пакетов для установки", "ok")
        return

    if any(pkg in KUBE_PACKAGES for pkg in missing):
        setup_kubernetes_repo()
        kube = KUBE_PACKAGES & missing
        if kube:
            install_kube_packages(kube)

    if "containerd" in missing:
        install_containerd()

    log("Установка завершена", "ok")

if __name__ == "__main__":
    install_missing()
