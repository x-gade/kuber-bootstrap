# cluster/check_cluster_health.py

import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log

KUBECONFIG_PATH = "/etc/kubernetes/admin.conf"

def check_health():
    os.environ["KUBECONFIG"] = KUBECONFIG_PATH

    try:
        result = subprocess.run(
            ["kubectl", "get", "--raw=/healthz"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        output = result.stdout.decode().strip()
        if output == "ok":
            log("kube-apiserver отвечает: /healthz → ok", "ok")
            return True
        else:
            log(f"kube-apiserver вернул: {output}", "warn")
            return False
    except subprocess.CalledProcessError as e:
        log("Ошибка при обращении к kube-apiserver", "error")
        print(e.stderr.decode())
        return False

if __name__ == "__main__":
    check_health()
