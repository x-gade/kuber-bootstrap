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


def write_config(include_flags: bool, bootstrap: bool = False) -> None:
    os.makedirs(CONF_PATH.parent, exist_ok=True)

    node_ip = collected_info.IP
    pod_cidr = calculate_pod_cidr(collected_info.CLUSTER_POD_CIDR, int(collected_info.CIDR))

    with open(CONF_PATH, "w") as f:
        f.write("[Service]\n")

        if include_flags:
            kubelet_extra_args = (
                f"--node-ip={node_ip} "
                f"--pod-cidr={pod_cidr} "
                f"--kubeconfig=/etc/kubernetes/kubelet.conf "
                f"--register-node=true "
                f"--fail-swap-on=false "
                f"--cgroup-driver=systemd "
                f"--container-runtime-endpoint=unix:///run/containerd/containerd.sock "
                f"--pod-infra-container-image=k8s.gcr.io/pause:3.9 "
                f"--cluster-dns=10.96.0.10 "
                f"--cluster-domain=cluster.local "
                f"--config=/var/lib/kubelet/config.yaml "
                f"--authentication-token-webhook=true "
                f"--authorization-mode=Webhook"
            )
            f.write(f'Environment="KUBELET_EXTRA_ARGS={kubelet_extra_args}"\n')
            f.write('ExecStart=\n')
            f.write('ExecStart=/usr/bin/kubelet $KUBELET_EXTRA_ARGS\n')

        elif bootstrap:
            kubelet_extra_args = (
                f"--container-runtime-endpoint=unix:///run/containerd/containerd.sock "
                f"--node-ip={node_ip} "
                f"--fail-swap-on=false "
                f"--cgroup-driver=systemd "
                f"--pod-infra-container-image=k8s.gcr.io/pause:3.9 "
                f"--register-node=false "
                f"--cluster-dns=10.96.0.10 "
                f"--cluster-domain=cluster.local "
                f"--config=/var/lib/kubelet/config.yaml"
            )
            f.write(f'Environment="KUBELET_EXTRA_ARGS={kubelet_extra_args}"\n')
            f.write('ExecStart=\n')
            f.write('ExecStart=/usr/bin/kubelet $KUBELET_EXTRA_ARGS\n')

        else:
            # memory-only: не указываем параметры — сохраняем ExecStart
            f.write('ExecStart=\n')
            f.write('ExecStart=/usr/bin/kubelet $KUBELET_EXTRA_ARGS\n')

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
    parser.add_argument(
        "--mode",
        choices=["memory", "flags", "bootstrap"],
        required=True,
        help="memory - только ограничения памяти; flags - финальная настройка; bootstrap — запуск без подключения к API"
    )
    args = parser.parse_args()

    if args.mode == "memory":
        log("=== Применение ограничений памяти для kubelet ===")
        write_config(include_flags=False)
        reload_systemd(restart=False)
        log("Перезапуск kubelet НЕ выполняется — он будет произведён на следующем этапе", "info")

    elif args.mode == "bootstrap":
        log("=== Минимальная конфигурация kubelet для bootstrap-режима ===")
        write_config(include_flags=False, bootstrap=True)
        reload_systemd(restart=True)

    elif args.mode == "flags":
        log("=== Применение параметров kubelet и перезапуск ===")
        write_config(include_flags=True)
        reload_systemd(restart=True)


if __name__ == "__main__":
    main()
