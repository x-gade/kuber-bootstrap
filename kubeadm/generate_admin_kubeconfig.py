# kubeadm/generate_admin_kubeconfig.py

import yaml
from pathlib import Path

KUBECONFIG_PATH = Path("/etc/kubernetes/admin.conf")
PROFILE_EXPORT_PATH = Path("/etc/profile.d/set-kubeconfig.sh")

def log(msg, level="info"):
    levels = {
        "info": "[INFO]",
        "ok": "[OK]",
        "warn": "[WARN]",
        "error": "[ERROR]"
    }
    print(f"{levels.get(level, '[INFO]')} {msg}")

def generate_admin_kubeconfig():
    log("Генерация admin.kubeconfig...")

    kubeconfig = {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [{
            "name": "kubernetes",
            "cluster": {
                "certificate-authority": "/etc/kubernetes/pki/ca.crt",
                "server": "https://127.0.0.1:6443"
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

    KUBECONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(KUBECONFIG_PATH, "w") as f:
        yaml.safe_dump(kubeconfig, f, sort_keys=False)
    log(f"Kubeconfig сгенерирован: {KUBECONFIG_PATH}", "ok")

    # Автоэкспорт переменной
    export_line = f'export KUBECONFIG={KUBECONFIG_PATH}\n'
    with open(PROFILE_EXPORT_PATH, "w") as f:
        f.write(export_line)
    log(f"Экспорт KUBECONFIG добавлен в: {PROFILE_EXPORT_PATH}", "ok")


if __name__ == "__main__":
    generate_admin_kubeconfig()
