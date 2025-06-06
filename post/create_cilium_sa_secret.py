#!/usr/bin/env python3

import os
import sys
import subprocess
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log

def run(cmd, check=True):
    log(f"[CMD] {cmd}", level="info")
    subprocess.run(cmd, shell=True, check=check)

def main():
    log("Создание ServiceAccount cilium...", level="info")
    run("kubectl create serviceaccount cilium -n kube-system || true")

    log("Создание Secret с привязкой к ServiceAccount cilium...", level="info")

    secret_manifest = """
apiVersion: v1
kind: Secret
metadata:
  name: cilium-token
  namespace: kube-system
  annotations:
    kubernetes.io/service-account.name: cilium
type: kubernetes.io/service-account-token
"""

    try:
        run(f"echo '{secret_manifest}' | kubectl apply -f -")
    except subprocess.CalledProcessError:
        log("Ошибка при создании или применении Secret", level="error")
        return

    log("ServiceAccount и Secret для Cilium успешно созданы.", level="ok")

if __name__ == "__main__":
    main()
