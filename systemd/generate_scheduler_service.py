#!/usr/bin/env python3

"""
<<<<<<< HEAD
Генерация systemd unit-файла и запуск kube-scheduler.
Generates a systemd unit file and launches kube-scheduler.
=======
Generates a systemd unit file and starts the kube-scheduler component.
Генерирует systemd unit-файл и запускает компонент kube-scheduler.
>>>>>>> origin/test
"""

import os
import sys
import shutil
import subprocess
import urllib.request
import yaml
from pathlib import Path
from jinja2 import Template

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from utils.logger import log
from data import collected_info

TEMPLATE_PATH = BASE_DIR / "data/systemd/scheduler.service.j2"
SERVICE_PATH = Path("/etc/systemd/system/kube-scheduler.service")
CONFIG_DIR = "/etc/kubernetes"
KUBECONFIG_PATH = CONFIG_DIR + "/scheduler.conf"
REQUIRED_BINARIES_PATH = BASE_DIR / "data/required_binaries.yaml"


def load_required_version():
<<<<<<< HEAD
=======
    """
    Load required kube-scheduler version and path from YAML config.
    Загружает требуемую версию и путь до kube-scheduler из YAML-файла.
    """
>>>>>>> origin/test
    if not REQUIRED_BINARIES_PATH.exists():
        log(f"Файл {REQUIRED_BINARIES_PATH} не найден", "error")
        sys.exit(1)

    with REQUIRED_BINARIES_PATH.open() as f:
        data = yaml.safe_load(f)

    entry = data.get("kube-scheduler")
    if not entry:
        log("Нет записи о kube-scheduler в required_binaries.yaml", "error")
        sys.exit(1)

    return entry["version"], entry["path"]


def download_binary(version, path):
<<<<<<< HEAD
=======
    """
    Download the kube-scheduler binary from the official release.
    Загружает бинарник kube-scheduler с официального источника.
    """
>>>>>>> origin/test
    if os.path.exists(path):
        log(f"Бинарник уже установлен: {path}", "ok")
        return

    url = f"https://dl.k8s.io/release/{version}/bin/linux/amd64/kube-scheduler"
    log(f"Скачиваем kube-scheduler {version} из {url}", "info")

    try:
        urllib.request.urlretrieve(url, path)
        os.chmod(path, 0o755)
        log(f"Установлен в {path}", "ok")
    except Exception as e:
        log(f"Ошибка при скачивании: {e}", "error")
        sys.exit(1)


def generate_unit_file(bin_path):
<<<<<<< HEAD
=======
    """
    Render and write the systemd unit file for kube-scheduler.
    Рендерит и записывает systemd unit-файл для kube-scheduler.
    """
>>>>>>> origin/test
    if not TEMPLATE_PATH.exists():
        log(f"Шаблон systemd unit не найден: {TEMPLATE_PATH}", "error")
        sys.exit(1)

    with TEMPLATE_PATH.open() as f:
        template = Template(f.read())

    rendered = template.render(
        bin_path=bin_path,
        config_dir=CONFIG_DIR
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
<<<<<<< HEAD
=======
    """
    Ensure scheduler.conf exists, generate with kubeadm if missing.
    Проверяет наличие scheduler.conf, создаёт через kubeadm при отсутствии.
    """
>>>>>>> origin/test
    if Path(KUBECONFIG_PATH).exists():
        log("Файл scheduler.conf уже существует", "ok")
        return

    log("Генерация scheduler.conf через kubeadm", "step")
    try:
        subprocess.run(
            ["kubeadm", "init", "phase", "kubeconfig", "scheduler"],
            check=True
        )
        log("scheduler.conf успешно сгенерирован", "ok")
    except subprocess.CalledProcessError as e:
        log(f"Ошибка при генерации kubeconfig: {e}", "error")
        sys.exit(1)


def reload_and_start():
<<<<<<< HEAD
=======
    """
    Reload systemd and start kube-scheduler service.
    Перезагружает systemd и запускает сервис kube-scheduler.
    """
>>>>>>> origin/test
    try:
        subprocess.run(["systemctl", "daemon-reexec"], check=True)
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "restart", "kube-scheduler"], check=True)
        subprocess.run(["systemctl", "enable", "kube-scheduler"], check=True)
        log("kube-scheduler запущен и включён в автозагрузку", "ok")
    except subprocess.CalledProcessError as e:
        log(f"Ошибка при перезапуске сервиса: {e}", "error")
        sys.exit(1)


def main():
<<<<<<< HEAD
=======
    """
    Main entrypoint: generate kube-scheduler service and start it.
    Главная точка входа: генерирует сервис kube-scheduler и запускает его.
    """
>>>>>>> origin/test
    log("=== Генерация systemd для kube-scheduler ===", "info")
    ensure_kubeconfig()
    version, path = load_required_version()
    download_binary(version, path)
    generate_unit_file(path)
    reload_and_start()


if __name__ == "__main__":
    main()
