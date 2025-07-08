# post/network_patch.py

"""
Enables IP forwarding for Kubernetes nodes.
Включает пересылку IP-пакетов для узлов Kubernetes.
"""

import os
import subprocess
from pathlib import Path
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log

def enable_ip_forwarding():
    """
    Enables kernel-level IP forwarding both temporarily and persistently.
    Включает IP forwarding в ядре как временно, так и на постоянной основе.
    """
    try:
        log("Включаю ip_forward (временное значение)...", "info")
        with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
            f.write("1")

        log("Обновляю /etc/sysctl.conf (постоянное значение)...", "info")
        sysctl_conf = Path("/etc/sysctl.conf")
        lines = sysctl_conf.read_text().splitlines()

        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith("net.ipv4.ip_forward"):
                lines[i] = "net.ipv4.ip_forward=1"
                found = True
                break

        if not found:
            lines.append("net.ipv4.ip_forward=1")

        sysctl_conf.write_text("\n".join(lines) + "\n")

        log("Применяю настройки через sysctl -p...", "info")
        subprocess.run(["sysctl", "-p"], check=True)

        log("IP forwarding успешно включён", "ok")

    except Exception as e:
        log(f"Ошибка при включении ip_forward: {e}", "error")


if __name__ == "__main__":
    enable_ip_forwarding()
