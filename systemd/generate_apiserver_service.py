# systemd/generate_apiserver_service.py

import os
import sys
import subprocess
import yaml
import urllib.request
import shutil
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data import collected_info

REQUIRED_BINARIES_PATH = Path("data/required_binaries.yaml")
SERVICE_PATH = "/etc/systemd/system/kube-apiserver.service"
MANIFESTS_DIR = "/etc/kubernetes/manifests"
CERT_DIR = "/etc/kubernetes/pki"
CONFIG_PATH = Path("data/apiserver_config")


def remove_pod_manifest():
    manifest_path = os.path.join(MANIFESTS_DIR, "kube-apiserver.yaml")
    if os.path.exists(manifest_path):
        os.remove(manifest_path)
        log(f"Удалён pod-манифест: {manifest_path}", "warn")


def load_required_version():
    with open(REQUIRED_BINARIES_PATH, "r") as f:
        binaries = yaml.safe_load(f)
    if "kube-apiserver" not in binaries:
        log("Отсутствует запись о kube-apiserver в required_binaries.yaml", "error")
        sys.exit(1)
    version = binaries["kube-apiserver"]["version"]
    path = binaries["kube-apiserver"]["path"]
    return version, path


def download_binary(version, path):
    if os.path.exists(path):
        log(f"Бинарник уже установлен: {path}", "ok")
        return

    url = f"https://dl.k8s.io/release/{version}/bin/linux/amd64/kube-apiserver"
    log(f"Скачивание kube-apiserver {version} из {url}...", "info")
    try:
        urllib.request.urlretrieve(url, path)
        os.chmod(path, 0o755)
        log(f"Бинарник установлен в: {path}", "ok")
    except Exception as e:
        log(f"Ошибка при скачивании kube-apiserver: {e}", "error")
        sys.exit(1)


def load_flag_lines():
    if not CONFIG_PATH.exists():
        log(f"Файл конфигурации параметров не найден: {CONFIG_PATH}", "error")
        sys.exit(1)

    with open(CONFIG_PATH, "r") as f:
        lines = f.readlines()

    flags = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.replace("{IP}", collected_info.IP)
        line = line.replace("{CERT_DIR}", CERT_DIR)
        flags.append(line)
    return " \\\n  ".join(flags)


def generate_unit_file(path):
    flags = load_flag_lines()

    unit_content = f"""[Unit]
Description=Kubernetes API Server
Documentation=https://kubernetes.io/docs/
After=network.target

[Service]
ExecStart={path} \\
  {flags}

Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

    if os.path.exists(SERVICE_PATH):
        with open(SERVICE_PATH, "r") as f:
            current_content = f.read()
        if current_content == unit_content:
            log("Unit-файл уже актуален, изменений не требуется", "ok")
            return
        backup_path = SERVICE_PATH + ".bak"
        shutil.copy(SERVICE_PATH, backup_path)
        log(f"Unit-файл отличается. Создана резервная копия: {backup_path}", "warn")

    with open(SERVICE_PATH, "w") as f:
        f.write(unit_content)
    log(f"Unit-файл обновлён: {SERVICE_PATH}", "ok")


def reload_and_start():
    subprocess.run(["systemctl", "daemon-reexec"], check=True)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "--now", "kube-apiserver"], check=True)
    log("kube-apiserver запущен и добавлен в автозагрузку", "ok")


def main():
    log("=== Настройка systemd-сервиса kube-apiserver ===", "info")
    remove_pod_manifest()
    version, path = load_required_version()
    download_binary(version, path)
    generate_unit_file(path)
    reload_and_start()


if __name__ == "__main__":
    main()
