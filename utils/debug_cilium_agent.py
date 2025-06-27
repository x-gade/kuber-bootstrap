#!/usr/bin/env python3
"""
Deep diagnostics for cilium-agent systemd launch issues.
Глубокая диагностика проблем запуска cilium-agent через systemd.
"""

import os
import sys
import socket
import subprocess
from pathlib import Path

# Добавляем путь до корня проекта для импорта внутренних модулей
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data import collected_info

# Глобальные параметры
KUBECONFIG = "/etc/kubernetes/admin.conf"
NODE_NAME = collected_info.HOSTNAME
NODE_IP = collected_info.IP
POD_CIDR = collected_info.CLUSTER_POD_CIDR


def check_file(path: str):
    """
    Checks if the file exists.
    Проверяет существование файла.
    """
    if Path(path).exists():
        log(f"Файл найден: {path}", "ok")
        return True
    else:
        log(f"Файл не найден: {path}", "error")
        return False


def check_ip_on_interface(ip: str):
    """
    Verifies that IP is assigned to at least one interface.
    Проверяет наличие IP на сетевых интерфейсах.
    """
    output = subprocess.getoutput("ip -o addr")
    if ip in output:
        log(f"IP {ip} найден на одном из интерфейсов", "ok")
        return True
    else:
        log(f"IP {ip} не найден ни на одном из интерфейсов", "error")
        return False


def check_kubeconfig():
    """
    Tests if the kubeconfig file allows querying cluster state.
    Проверяет доступность кластера через kubeconfig.
    """
    cmd = f"kubectl --kubeconfig={KUBECONFIG} get node"
    result = subprocess.run(cmd.split(), capture_output=True, text=True)
    if result.returncode == 0:
        log("kubeconfig работает, кластер доступен", "ok")
        return True
    else:
        log("kubeconfig недоступен или кластер недоступен", "error")
        return False


def check_node_registered():
    """
    Verifies if current node is registered in Kubernetes.
    Проверяет, зарегистрирован ли узел в Kubernetes.
    """
    cmd = f"kubectl --kubeconfig={KUBECONFIG} get node {NODE_NAME}"
    result = subprocess.run(cmd.split(), capture_output=True, text=True)
    if result.returncode == 0:
        log(f"Node {NODE_NAME} зарегистрирован в Kubernetes", "ok")
        return True
    else:
        log(f"Node {NODE_NAME} НЕ зарегистрирован в Kubernetes", "error")
        log("Возможная причина: kubelet не зарегистрировал узел", "warn")
        return False


def check_sysfs_bpf():
    """
    Ensures BPF mountpoint is active.
    Проверяет, смонтирован ли /sys/fs/bpf.
    """
    if os.path.ismount("/sys/fs/bpf"):
        log("/sys/fs/bpf смонтирован", "ok")
        return True
    else:
        log("/sys/fs/bpf НЕ смонтирован", "error")
        return False


def check_cni_conflict():
    """
    Detects old or conflicting CNI configs in /etc/cni/net.d.
    Проверяет наличие конфликтующих конфигураций CNI.
    """
    netdir = Path("/etc/cni/net.d")
    if not netdir.exists() or not any(netdir.iterdir()):
        log("CNI конфигурация отсутствует — ок", "ok")
        return
    log("Обнаружены файлы в /etc/cni/net.d:", "warn")
    for f in netdir.iterdir():
        log(f"  └─ {f.name}", "warn")


def check_interface_conflict():
    """
    Detects conflicting interfaces like cni0 or flannel.
    Проверяет наличие конфликтующих интерфейсов (cni0, flannel.1 и т.п.).
    """
    output = subprocess.getoutput("ip link show")
    for iface in ["cni0", "flannel.1"]:
        if iface in output:
            log(f"Интерфейс {iface} существует — возможен конфликт CNI", "warn")


def check_config_dir():
    """
    Looks for any YAML files in /etc/cilium that may interfere.
    Ищет YAML-конфигурации в /etc/cilium, которые могут повлиять.
    """
    config_dir = Path("/etc/cilium")
    yamls = list(config_dir.glob("*.yaml")) + list(config_dir.glob("*.yml"))
    if not yamls:
        log("Конфигурационные YAML-файлы в /etc/cilium отсутствуют", "ok")
    else:
        log("Обнаружены нестандартные YAML-файлы в /etc/cilium:", "warn")
        for y in yamls:
            log(f"  └─ {y.name}", "warn")


def main():
    """
    Entry point for diagnostics.
    Точка входа для диагностики.
    """
    log("=== Диагностика запуска cilium-agent ===", "info")

    check_file(KUBECONFIG)
    check_ip_on_interface(NODE_IP)
    if check_kubeconfig():
        check_node_registered()
    check_sysfs_bpf()
    check_config_dir()
    check_cni_conflict()
    check_interface_conflict()

    log("Диагностика завершена.", "info")


if __name__ == "__main__":
    main()
