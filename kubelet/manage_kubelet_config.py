#!/usr/bin/env python3
"""
Manage systemd kubelet config by applying Jinja2 templates.
Генерация systemd-конфига kubelet с помощью шаблонов Jinja2.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import ipaddress

# Добавление корня проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data import collected_info

# Пути к шаблонам и выходному конфигу
TEMPLATE_DIR = Path("data/10-kubelet.conf")
OUTPUT_PATH = Path("/etc/systemd/system/kubelet.service.d/10-kubeadm.conf")


def calculate_pod_cidr(cluster_cidr: str, new_prefix: int, index: int = 0) -> str:
    """
    Calculate a sub-CIDR block from the given cluster network.
    Вычисляет подсеть из основной сети подов для конкретного узла.
    """
    subnets = list(ipaddress.IPv4Network(cluster_cidr).subnets(new_prefix=new_prefix))
    return str(subnets[index])


def render_template(mode: str):
    """
    Render kubelet systemd override template based on selected mode.
    Генерирует шаблонный systemd-конфиг kubelet в заданном режиме.

    Modes:
      - memory:     ограничение памяти без перезапуска kubelet
      - bootstrap:  урезанный конфиг для начального запуска kubelet
      - flags:      финальный полноценный конфиг с флагами --pod-cidr и --node-ip
    """
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template_name = {
        "memory": "memory-step.conf.j2",
        "bootstrap": "bootstrap-step.conf.j2",
        "flags": "flags-step.conf.j2"
    }.get(mode)

    if not template_name:
        log(f"Неизвестный режим шаблона: {mode}", "error")
        sys.exit(1)

    template = env.get_template(template_name)

    pod_cidr = calculate_pod_cidr(collected_info.CLUSTER_POD_CIDR, int(collected_info.CIDR))

    rendered = template.render(
        node_ip=collected_info.IP,
        pod_cidr=pod_cidr
    )

    os.makedirs(OUTPUT_PATH.parent, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(rendered)

    log(f"Файл {OUTPUT_PATH} сгенерирован из шаблона {template_name}", "ok")


def reload_systemd(restart: bool = False):
    """
    Reload systemd and optionally restart kubelet.
    Перезапускает systemd и (по необходимости) перезапускает kubelet.
    """
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
    """
    Entry point: parses args, renders template, and reloads kubelet.
    Точка входа: парсит аргументы, применяет шаблон и перезапускает kubelet при необходимости.
    """
    parser = argparse.ArgumentParser(description="Генерация 10-kubelet.conf через шаблон")
    parser.add_argument(
        "--mode",
        choices=["memory", "flags", "bootstrap"],
        required=True,
        help="memory — ограничение памяти, bootstrap — урезанный старт, flags — финальные флаги"
    )
    args = parser.parse_args()

    log(f"==> Применение шаблона kubelet ({args.mode})", "info")
    render_template(args.mode)

    if args.mode == "memory":
        log("Перезапуск kubelet НЕ требуется на этом этапе", "info")
    else:
        reload_systemd(restart=True)


if __name__ == "__main__":
    main()
