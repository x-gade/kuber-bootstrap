#!/usr/bin/env python3

"""
Генерация systemd unit-файла и запуск kube-controller-manager.
Generates a systemd unit file and launches kube-controller-manager.
"""

import os
import sys
import shutil
import subprocess
import urllib.request
import yaml
from pathlib import Path
from jinja2 import Template

# Добавим путь до корня проекта
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from utils.logger import log
from data import collected_info

# Константы
TEMPLATE_PATH = BASE_DIR / "data/systemd/controller_manager.service.j2"
SERVICE_PATH = Path("/etc/systemd/system/kube-controller-manager.service")
CERT_DIR = "/etc/kubernetes/pki"
CONFIG_DIR = "/etc/kubernetes"
KUBECONFIG_PATH = CONFIG_DIR + "/controller-manager.conf"
REQUIRED_BINARIES_PATH = BASE_DIR / "data/required_binaries.yaml"


def load_required_version():
    """
    Загружает версию и путь к бинарнику из required_binaries.yaml.
    Loads the version and path to the binary from required_binaries.yaml.
    """

    if not REQUIRED_BINARIES_PATH.exists():
        log(f"Файл {REQUIRED_BINARIES_PATH} не найден", "error")
        sys.exit(1)

    with REQUIRED_BINARIES_PATH.open() as f:
        data = yaml.safe_load(f)

    entry = data.get("kube-controller-manager")
    if not entry:
        log("Нет записи о kube-controller-manager в required_binaries.yaml", "error")
        sys.exit(1)

    return entry["version"], entry["path"]


def download_binary(version, path):
    """
    Скачивает бинарник kube-controller-manager, если он ещё не установлен.
    Downloads the kube-controller-manager binary if it's not already installed.
    """

    if os.path.exists(path):
        log(f"Бинарник уже установлен: {path}", "ok")
        return

    url = f"https://dl.k8s.io/release/{version}/bin/linux/amd64/kube-controller-manager"
    log(f"Скачиваем kube-controller-manager {version} из {url}", "info")

    try:
        urllib.request.urlretrieve(url, path)
        os.chmod(path, 0o755)
        log(f"Установлен в {path}", "ok")
    except Exception as e:
        log(f"Ошибка при скачивании: {e}", "error")
        sys.exit(1)


def generate_unit_file(bin_path):
    """
    Генерирует systemd unit-файл из шаблона и сохраняет его.
    Generates a systemd unit file from template and saves it.
    """

    cluster_cidr = getattr(collected_info, "CLUSTER_POD_CIDR", "10.244.0.0/16")

    if not TEMPLATE_PATH.exists():
        log(f"Шаблон systemd unit не найден: {TEMPLATE_PATH}", "error")
        sys.exit(1)

    with TEMPLATE_PATH.open() as f:
        template = Template(f.read())

    rendered = template.render(
        bin_path=bin_path,
        config_dir=CONFIG_DIR,
        cert_dir=CERT_DIR,
        cluster_cidr=cluster_cidr
    )

    if SERVICE_PATH.exists():
        with SERVICE_PATH.open() as f:
            current = f.read()
        if current == rendered:
            log("Unit-файл уже актуален, перезапускаем", "warn")
        else:
            backup = SERVICE_PATH.with_suffix(".service.bak")
            shutil.copy(SERVICE_PATH, backup)
            log(f"Unit-файл отличается. Создана резервная копия: {backup}", "warn")

    with SERVICE_PATH.open("w") as f:
        f.write(rendered)

    log(f"Unit-файл обновлён: {SERVICE_PATH}", "ok")


def ensure_kubeconfig():
    """
    Проверяет существование controller-manager.conf, генерирует его при необходимости.
    Checks if controller-manager.conf exists and generates it if missing.
    """

    if Path(KUBECONFIG_PATH).exists():
        log("Файл controller-manager.conf уже существует", "ok")
        return

    log("Генерация controller-manager.conf через kubeadm", "step")
    try:
        subprocess.run(
            ["kubeadm", "init", "phase", "kubeconfig", "controller-manager"],
            check=True
        )
        log("controller-manager.conf успешно сгенерирован", "ok")
    except subprocess.CalledProcessError as e:
        log(f"Ошибка при генерации kubeconfig: {e}", "error")
        sys.exit(1)


def reload_and_start():
    """
    Перезапускает systemd, активирует и запускает сервис.
    Reloads systemd, enables and starts the service.
    """

    try:
        subprocess.run(["systemctl", "daemon-reexec"], check=True)
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "restart", "kube-controller-manager"], check=True)
        subprocess.run(["systemctl", "enable", "kube-controller-manager"], check=True)
        log("kube-controller-manager запущен и включён в автозагрузку", "ok")
    except subprocess.CalledProcessError as e:
        log(f"Ошибка при перезапуске сервиса: {e}", "error")
        sys.exit(1)


def main():
    """
    Основная точка входа: полная установка и запуск kube-controller-manager.
    Main entry point: full setup and launch of kube-controller-manager.
    """

    log("=== Генерация systemd для kube-controller-manager ===", "info")
    ensure_kubeconfig()
    version, path = load_required_version()
    download_binary(version, path)
    generate_unit_file(path)
    reload_and_start()


if __name__ == "__main__":
    main()
