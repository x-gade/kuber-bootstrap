#!/usr/bin/env python3

import os
import shutil
import sys
from pathlib import Path
from jinja2 import Template
import ipaddress

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log
from data import collected_info

TEMPLATE_SRC = "data/kubelet_override.conf"  # теперь Jinja-шаблон
TARGET_DIR = "/etc/systemd/system/kubelet.service.d"
TARGET_PATH = os.path.join(TARGET_DIR, "99-override-memory.conf")

def calculate_pod_cidr(cluster_cidr: str, new_prefix: int, index: int = 0) -> str:
    subnets = list(ipaddress.IPv4Network(cluster_cidr).subnets(new_prefix=new_prefix))
    return str(subnets[index])

def render_template():
    if not os.path.exists(TEMPLATE_SRC):
        log(f"Файл шаблона не найден: {TEMPLATE_SRC}", "error")
        sys.exit(1)

    with open(TEMPLATE_SRC) as f:
        template = Template(f.read())

    role = collected_info.ROLE
    pod_cidr = calculate_pod_cidr(collected_info.CLUSTER_POD_CIDR, int(collected_info.CIDR))

    result = template.render(role=role, pod_cidr=pod_cidr)

    os.makedirs(TARGET_DIR, exist_ok=True)
    with open(TARGET_PATH, "w") as f:
        f.write(result)

    log(f"Override-файл сгенерирован и записан в: {TARGET_PATH}", "ok")

def reload_systemd():
    os.system("systemctl daemon-reexec")
    os.system("systemctl daemon-reload")
    log("Systemd перезагружен", "ok")

def main():
    render_template()
    reload_systemd()
    log("Перезапуск kubelet НЕ выполняется — он будет произведён на следующем этапе", "info")

if __name__ == "__main__":
    main()
