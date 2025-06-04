#!/usr/bin/env python3

import argparse
import os
import subprocess
import ipaddress
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log
from data import collected_info

CONF_PATH = Path("/etc/systemd/system/kubelet.service.d/10-kubeadm.conf")


def calculate_pod_cidr(cluster_cidr: str, new_prefix: int, index: int = 0) -> str:
    subnets = list(ipaddress.IPv4Network(cluster_cidr).subnets(new_prefix=new_prefix))
    return str(subnets[index])


def write_config(include_flags: bool) -> None:
    os.makedirs(CONF_PATH.parent, exist_ok=True)

    role = collected_info.ROLE
    node_ip = collected_info.IP
    pod_cidr = calculate_pod_cidr(collected_info.CLUSTER_POD_CIDR, int(collected_info.CIDR))

    with open(CONF_PATH, "w") as f:
        f.write("[Service]\n")
        if include_flags:
            kubelet_extra_args = (
                f"--allow-privileged=true "
                f"--node-ip={node_ip} "
                f"--node-labels=node-role.kubernetes.io/{role}= "
                f"--register-with-taints=node-role.kubernetes.io/{role}=:NoSchedule "
                f"--pod-cidr={pod_cidr}"
            )
            f.write(f'Environment="KUBELET_EXTRA_ARGS={kubelet_extra_args}"\n')
            f.write('ExecStart=\n')
            f.write('ExecStart=/usr/bin/kubelet $KUBELET_KUBECONFIG_ARGS $KUBELET_CONFIG_ARGS $KUBELET_EXTRA_ARGS\n')
        f.write('EnvironmentFile=-/var/lib/kubelet/kubeadm-flags.env\n')
        f.write('MemoryMax=4G\n')
        f.write('OOMScoreAdjust=-999\n')
        f.write('Delegate=yes\n')
        f.write('Slice=kubelet.slice\n')

    log(f"Файл {CONF_PATH} сформирован", "ok")


def reload_systemd(restart: bool = False) -> None:
    subprocess.run(["systemctl", "daemon-reexec"], check=True)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    if restart:
        subprocess.run(["systemctl", "restart", "kubelet"], check=True)
        log("kubelet перезапущен", "ok")

        result = subprocess.run(["systemctl", "is-active", "kubelet"], capture_output=True, text=True)
        status = result.stdout.strip()
        if status == "active":
            log("kubelet работает нормально после перезапуска", "ok")
        else:
            log(f"kubelet не запущен (status: {status}) — проверь логи через 'journalctl -u kubelet'", "error")


def main():
    parser = argparse.ArgumentParser(description="Управление конфигурацией kubelet")
    parser.add_argument("--mode", choices=["memory", "flags"], required=True,
                        help="memory - записать ограничения памяти, flags - задать параметры kubelet и перезапустить")
    args = parser.parse_args()

    if args.mode == "memory":
        log("=== Применение ограничений памяти для kubelet ===")
        write_config(include_flags=False)
        reload_systemd(restart=False)
        log("Перезапуск kubelet НЕ выполняется — он будет произведён на следующем этапе", "info")
    else:
        log("=== Применение параметров kubelet и перезапуск ===")
        write_config(include_flags=True)
        reload_systemd(restart=True)


if __name__ == "__main__":
    main()
