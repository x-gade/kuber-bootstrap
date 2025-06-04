# kubelet/patch_kubelet_args.py

import os
import sys
import subprocess
from pathlib import Path
import ipaddress

# Подключаем collected_info
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from data import collected_info

KUBELET_CONF_PATH = Path("/etc/systemd/system/kubelet.service.d/10-kubeadm.conf")

def log(msg, level="info"):
    levels = {
        "info": "[INFO]",
        "ok": "[OK]",
        "warn": "[WARN]",
        "error": "[ERROR]"
    }
    print(f"{levels.get(level, '[INFO]')} {msg}")

def calculate_pod_cidr(cluster_cidr: str, new_prefix: int, index: int = 0) -> str:
    subnets = list(ipaddress.IPv4Network(cluster_cidr).subnets(new_prefix=new_prefix))
    return str(subnets[index])

def patch_kubelet_args():
    role = collected_info.ROLE
    node_ip = collected_info.IP
    pod_cidr = calculate_pod_cidr(collected_info.CLUSTER_POD_CIDR, int(collected_info.CIDR))

    kubelet_extra_args = (
        f'--allow-privileged=true '
        f'--node-ip={node_ip} '
        f'--node-labels=node-role.kubernetes.io/{role}= '
        f'--register-with-taints=node-role.kubernetes.io/{role}=:NoSchedule '
        f'--pod-cidr={pod_cidr}'
    )

    env_line = f'Environment="KUBELET_EXTRA_ARGS={kubelet_extra_args}"\n'
    exec_line = (
        'ExecStart=\n'
        'ExecStart=/usr/bin/kubelet $KUBELET_KUBECONFIG_ARGS '
        '$KUBELET_CONFIG_ARGS $KUBELET_EXTRA_ARGS\n'
    )

    if not KUBELET_CONF_PATH.parent.exists():
        log(f"Создаю директорию {KUBELET_CONF_PATH.parent}...", "info")
        KUBELET_CONF_PATH.parent.mkdir(parents=True, exist_ok=True)

    if KUBELET_CONF_PATH.exists():
        with open(KUBELET_CONF_PATH, "r") as f:
            if "--node-labels" in f.read():
                log("Флаги уже указаны в 10-kubeadm.conf", "ok")
                return

    with open(KUBELET_CONF_PATH, "w") as f:
        f.write("[Service]\n")
        f.write(env_line)
        f.write(exec_line)

    log("Файл 10-kubeadm.conf успешно перезаписан с необходимыми параметрами", "ok")

def reload_systemd():
    subprocess.run(["systemctl", "daemon-reexec"], check=True)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "restart", "kubelet"], check=True)
    log("kubelet перезапущен", "ok")

    result = subprocess.run(["systemctl", "is-active", "kubelet"], capture_output=True, text=True)
    status = result.stdout.strip()
    if status == "active":
        log("kubelet работает нормально после перезапуска", "ok")
    else:
        log(f"kubelet не запущен (status: {status}) — проверь логи через 'journalctl -u kubelet'", "error")

def main():
    log("=== Патчинг systemd конфигурации kubelet ===")
    patch_kubelet_args()
    reload_systemd()

if __name__ == "__main__":
    main()
