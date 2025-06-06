#!/usr/bin/env python3

import os
import sys
import shutil
import subprocess
from pathlib import Path
from jinja2 import Template

# Добавляем путь до корня проекта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data import collected_info

# Пути
TEMPLATE_PATH = "data/systemd/controller_manager.service.j2"
SERVICE_PATH = "/etc/systemd/system/kube-controller-manager.service"
CERT_DIR = "/etc/kubernetes/pki"
CONFIG_DIR = "/etc/kubernetes"

def load_required_version():
    import yaml
    REQUIRED_BINARIES_PATH = "data/required_binaries.yaml"
    with open(REQUIRED_BINARIES_PATH, "r") as f:
        data = yaml.safe_load(f)
    if "kube-controller-manager" not in data:
        log("Нет записи о kube-controller-manager в required_binaries.yaml", "error")
        sys.exit(1)
    return data["kube-controller-manager"]["version"], data["kube-controller-manager"]["path"]

def download_binary(version, path):
    if os.path.exists(path):
        log(f"Бинарник уже установлен: {path}", "ok")
        return
    url = f"https://dl.k8s.io/release/{version}/bin/linux/amd64/kube-controller-manager"
    log(f"Скачиваем kube-controller-manager {version} из {url}", "info")
    try:
        import urllib.request
        urllib.request.urlretrieve(url, path)
        os.chmod(path, 0o755)
        log(f"Установлен в {path}", "ok")
    except Exception as e:
        log(f"Ошибка при скачивании: {e}", "error")
        sys.exit(1)

def generate_unit_file(bin_path):
    # Берём CIDR из collected_info
    cluster_cidr = getattr(collected_info, "CLUSTER_POD_CIDR", "10.244.0.0/16")

    # Читаем шаблон и рендерим
    with open(TEMPLATE_PATH, "r") as f:
        template = Template(f.read())

    rendered = template.render(
        bin_path=bin_path,
        config_dir=CONFIG_DIR,
        cert_dir=CERT_DIR,
        cluster_cidr=cluster_cidr
    )

    changed = True
    if os.path.exists(SERVICE_PATH):
        with open(SERVICE_PATH, "r") as f:
            current = f.read()
        if current == rendered:
            log("Unit-файл уже актуален, но будет выполнен принудительный перезапуск", "warn")
            changed = False
        else:
            backup = SERVICE_PATH + ".bak"
            shutil.copy(SERVICE_PATH, backup)
            log(f"Unit-файл отличается. Создана резервная копия: {backup}", "warn")

    with open(SERVICE_PATH, "w") as f:
        f.write(rendered)

    if changed:
        log(f"Unit-файл обновлён: {SERVICE_PATH}", "ok")

def ensure_kubeconfig():
    kubeconfig_path = "/etc/kubernetes/controller-manager.conf"
    if os.path.exists(kubeconfig_path):
        log("Файл controller-manager.conf уже существует", "ok")
        return

    log("Генерация controller-manager.conf через kubeadm", "step")
    try:
        subprocess.run(["kubeadm", "init", "phase", "kubeconfig", "controller-manager"], check=True)
        log("controller-manager.conf успешно сгенерирован", "ok")
    except subprocess.CalledProcessError as e:
        log(f"Ошибка при генерации kubeconfig: {e}", "error")
        sys.exit(1)


def reload_and_start():
    subprocess.run(["systemctl", "daemon-reexec"], check=True)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "restart", "kube-controller-manager"], check=True)
    subprocess.run(["systemctl", "enable", "kube-controller-manager"], check=True)
    log("kube-controller-manager запущен и включён в автозагрузку", "ok")

def main():
    log("=== Генерация systemd для kube-controller-manager ===", "info")
    ensure_kubeconfig()
    version, path = load_required_version()
    download_binary(version, path)
    generate_unit_file(path)
    reload_and_start()

if __name__ == "__main__":
    main()
