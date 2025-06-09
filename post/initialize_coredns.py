#!/usr/bin/env python3

import subprocess
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log

KUBECONFIG_PATH = "/etc/kubernetes/admin.conf"

def run(cmd: list, error_msg: str, exit_on_fail=True):
    try:
        subprocess.run(cmd, check=True)
        log("Успешно: " + " ".join(cmd), "ok")
    except subprocess.CalledProcessError:
        log(error_msg, "error")
        if exit_on_fail:
            sys.exit(1)

def main():
    log("Экспорт переменной KUBECONFIG", "step")
    os.environ["KUBECONFIG"] = KUBECONFIG_PATH

    log("Установка CoreDNS", "step")
    run(
        ["kubeadm", "init", "phase", "addon", "coredns"],
        "Ошибка при установке CoreDNS"
    )

    log("Готово! Проверка pod'ов через kubectl get pods -n kube-system", "step")
    try:
        subprocess.run(["kubectl", "get", "pods", "-n", "kube-system"])
    except Exception:
        log("Не удалось получить список pod'ов. Проверьте статус kubelet и CNI.", "warn")

if __name__ == "__main__":
    main()
