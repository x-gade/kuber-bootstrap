#!/usr/bin/env python3
import os
import subprocess
import time
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log
from data.collected_info import HOSTNAME, ROLE

LABEL = f"node-role.kubernetes.io/{ROLE}"

def wait_for_node(timeout=90, interval=3):
    for _ in range(int(timeout/interval)):
        result = subprocess.run([
            "kubectl", "get", "node", HOSTNAME
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            return True
        time.sleep(interval)
    return False

def label_node():
    cmd_label = [
        "kubectl", "label", "node", HOSTNAME,
        f"{LABEL}=" , "--overwrite"
    ]
    cmd_taint = [
        "kubectl", "taint", "nodes", HOSTNAME,
        f"{LABEL}=:NoSchedule", "--overwrite"
    ]
    subprocess.run(cmd_label, check=True)
    subprocess.run(cmd_taint, check=True)

def main():
    log("Ожидание регистрации ноды в кластере...", "info")
    if not wait_for_node():
        log("Нода не зарегистрировалась в отведённое время", "error")
        sys.exit(1)
    log("Назначение роли ноде и применение taint...", "info")
    try:
        label_node()
        log("Роль и taint назначены", "ok")
    except subprocess.CalledProcessError:
        log("Не удалось назначить роль или taint", "error")
        sys.exit(1)

if __name__ == "__main__":
    main()
