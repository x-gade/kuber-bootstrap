# collect_node_info.py

import os
import socket
import platform
import sys
from utils.logger import log

OUTPUT_FILE = "data/collected_info.py"
CLUSTER_POD_CIDR = "10.244.0.0/16"

def get_ip():
    """Получает внешний IP-адрес через сокет без внешних запросов"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        log(f"Не удалось определить IP-адрес: {e}", "error")
        return "127.0.0.1"

def collect_info(role="control-plane"):
    log("Сбор данных о машине...", "info")

    if role not in ["control-plane", "node"]:
        log("Недопустимая роль. Используйте: control-plane или node", "error")
        sys.exit(1)

    cidr = "26" if role == "control-plane" else "24"

    info = {
        "IP": get_ip(),
        "HOSTNAME": socket.gethostname(),
        "ARCH": platform.machine(),
        "DISTRO": platform.linux_distribution()[0] if hasattr(platform, 'linux_distribution') else platform.system(),
        "KERNEL": platform.release(),
        "ROLE": role,
        "CIDR": cidr,
        "CLUSTER_POD_CIDR": CLUSTER_POD_CIDR
    }

    with open(OUTPUT_FILE, "w") as f:
        for key, value in info.items():
            f.write(f'{key} = "{value}"\n')

    log(f"Данные сохранены в {OUTPUT_FILE}", "ok")

if __name__ == "__main__":
    if len(sys.argv) == 2:
        role_arg = sys.argv[1].strip().lower()
    else:
        role_arg = "control-plane"
        log("Аргумент роли не указан, использую по умолчанию: control-plane", "warn")

    collect_info(role=role_arg)
