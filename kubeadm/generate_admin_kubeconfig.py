# kubeadm/generate_admin_kubeconfig.py

import os
import sys
import yaml

# путь к корню проекта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data import collected_info

KUBECONFIG_PATH = "/etc/kubernetes/admin.conf"
EXPORT_SCRIPT_PATH = "/etc/profile.d/set-kubeconfig.sh"

def generate_kubeconfig():
    os.makedirs(os.path.dirname(KUBECONFIG_PATH), exist_ok=True)

    config = {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [{
            "name": "kubernetes",
            "cluster": {
                "certificate-authority": "/etc/kubernetes/pki/ca.crt",
                "server": f"https://{collected_info.IP}:6443"
            }
        }],
        "users": [{
            "name": "kubernetes-admin",
            "user": {
                "client-certificate": "/etc/kubernetes/pki/admin.crt",
                "client-key": "/etc/kubernetes/pki/admin.key"
            }
        }],
        "contexts": [{
            "name": "kubernetes-admin@kubernetes",
            "context": {
                "cluster": "kubernetes",
                "user": "kubernetes-admin"
            }
        }],
        "current-context": "kubernetes-admin@kubernetes"
    }

    with open(KUBECONFIG_PATH, "w") as f:
        yaml.dump(config, f, sort_keys=False, default_flow_style=False)

    log(f"Kubeconfig сгенерирован: {KUBECONFIG_PATH}", "ok")

    with open(EXPORT_SCRIPT_PATH, "w") as f:
        f.write(f'export KUBECONFIG="{KUBECONFIG_PATH}"\n')

    log(f"Экспорт KUBECONFIG добавлен в: {EXPORT_SCRIPT_PATH}", "ok")

if __name__ == "__main__":
    generate_kubeconfig()
