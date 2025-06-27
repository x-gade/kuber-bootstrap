#!/usr/bin/env python3
"""
Generates cilium_values.yaml from template, pulls Cilium images and installs the Helm chart  
Генерирует cilium_values.yaml из шаблона, загружает образы Cilium и устанавливает Helm-чарт
"""

import os
import sys
import subprocess
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from jinja2 import Template
from utils.logger import log

sys.path.append("data")
import collected_info

# ─── Константы ───
TEMPLATE_PATH = "data/cni/cilium_values.yaml.j2"
OUTPUT_PATH = "generated/cilium_values.yaml"
CA_PATH = "/etc/kubernetes/pki/ca.crt"

HELM_CHART = "cilium/cilium"
HELM_RELEASE = "cilium"
HELM_NAMESPACE = "kube-system"
CILIUM_VERSION = "1.17.5"

IMAGES = [
    f"quay.io/cilium/cilium:v{CILIUM_VERSION}",
    f"quay.io/cilium/operator-generic:v{CILIUM_VERSION}"
]


def load_ca_cert():
    """
    Loads the Kubernetes cluster CA certificate from the system path  
    Загружает CA-сертификат кластера Kubernetes из системного пути
    """
    if not os.path.isfile(CA_PATH):
        log(f"Файл сертификата не найден: {CA_PATH}", level="error")
        sys.exit(1)

    with open(CA_PATH, "r") as f:
        return f.read().strip()


def render_template(ca_crt: str):
    """
    Renders the Helm values.yaml template with collected server info and CA cert  
    Рендерит шаблон Helm values.yaml с данными сервера и CA-сертификатом
    """
    log("Рендеринг шаблона cilium_values.yaml...", level="info")

    with open(TEMPLATE_PATH, "r") as f:
        template = Template(f.read())

    context = {
        "IP": collected_info.IP,
        "CLUSTER_POD_CIDR": collected_info.CLUSTER_POD_CIDR,
        "OPERATOR_REPLICAS": 2,
        "ca_crt": ca_crt,
        "HOSTNAME": collected_info.HOSTNAME,
    }

    rendered = template.render(**context)

    Path(os.path.dirname(OUTPUT_PATH)).mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(rendered)

    log(f"Cilium values.yaml сгенерирован: {OUTPUT_PATH}", level="ok")


def pull_images():
    """
    Pulls required Docker images for Cilium and operator  
    Загружает необходимые Docker-образы Cilium и оператора
    """
    log("Загрузка Docker-образов Cilium...", level="info")

    for image in IMAGES:
        log(f"Загружается образ: {image}", level="info")
        result = subprocess.run(["docker", "pull", image], capture_output=True, text=True)
        if result.returncode != 0:
            log(f"Ошибка при загрузке {image}:\n{result.stderr}", level="error")
            sys.exit(1)
        log(f"Образ загружен: {image}", level="ok")


def helm_install():
    """
    Runs Helm install/upgrade for the Cilium chart using rendered values  
    Выполняет Helm install/upgrade для Cilium-чарта с сгенерированным values.yaml
    """
    log("Установка Helm-чарта Cilium...", level="info")

    cmd = [
        "helm", "upgrade", "--install", HELM_RELEASE, HELM_CHART,
        "--namespace", HELM_NAMESPACE,
        "--create-namespace",
        "-f", OUTPUT_PATH,
        "--version", CILIUM_VERSION
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"Helm завершился с ошибкой:\n{result.stderr}", level="error")
        sys.exit(1)

    log("Cilium успешно установлен через Helm", level="ok")


def restart_services():
    """
    Перезапускает containerd и kubelet после настройки маунтов
    Restart containerd and kubelet after preparing BPF and cgroup2 mounts
    """
    log("Перезапускаем containerd и kubelet после подготовки маунтов", "info")
    subprocess.run(["systemctl", "restart", "containerd"], check=True)
    subprocess.run(["systemctl", "restart", "kubelet"], check=True)
    log("Сервисы перезапущены успешно", "ok")


def main():
    """
    Main execution entrypoint for Cilium configuration, image pulling, and deployment  
    Главная точка входа для генерации конфигурации Cilium, загрузки образов и деплоя
    """
    log("==> Начало генерации и установки Cilium", level="info")
    ca_crt = load_ca_cert()
    render_template(ca_crt)
    pull_images()
    helm_install()
    log("==> Завершено: Cilium успешно установлен", level="ok")
    restart_services()

if __name__ == "__main__":
    main()
