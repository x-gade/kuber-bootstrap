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


def get_config_path(mode: str) -> Path:
    if mode == "dev":
        return Path("data/apiserver_config_dev")
    elif mode == "prod":
        return Path("data/apiserver_config_prod")
    else:
        log(f"Неизвестный режим: {mode}", "error")
        sys.exit(1)


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


def load_flag_lines(config_path: Path):
    if not config_path.exists():
        log(f"Файл конфигурации параметров не найден: {config_path}", "error")
        sys.exit(1)

    with open(config_path, "r") as f:
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


def generate_unit_file(binary_path, config_path):
    flags = load_flag_lines(config_path)
    with open("data/kube-apiserver.service.template", "r") as f:
        template = f.read()

    unit_content = template.replace("{BINARY_PATH}", binary_path).replace("{FLAGS}", flags)

    changed = True
    if os.path.exists(SERVICE_PATH):
        with open(SERVICE_PATH, "r") as f:
            current_content = f.read()
        if current_content == unit_content:
            log("Unit-файл уже актуален, но будет выполнен принудительный перезапуск", "warn")
            changed = False
        else:
            backup_path = SERVICE_PATH + ".bak"
            shutil.copy(SERVICE_PATH, backup_path)
            log(f"Unit-файл отличается. Создана резервная копия: {backup_path}", "warn")

    with open(SERVICE_PATH, "w") as f:
        f.write(unit_content)
    if changed:
        log(f"Unit-файл обновлён: {SERVICE_PATH}", "ok")


def reload_and_start():
    subprocess.run(["systemctl", "daemon-reexec"], check=True)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "restart", "kube-apiserver"], check=True)
    subprocess.run(["systemctl", "enable", "kube-apiserver"], check=True)
    log("kube-apiserver перезапущен и добавлен в автозагрузку", "ok")


def main():
    mode = "prod"
    if len(sys.argv) > 1 and sys.argv[1] == "--mode=dev":
        mode = "dev"
    log(f"=== Настройка kube-apiserver в режиме {mode.upper()} ===", "info")

    config_path = get_config_path(mode)
    remove_pod_manifest()
    version, path = load_required_version()
    download_binary(version, path)
    generate_unit_file(path, config_path)
    reload_and_start()

    if mode in ("dev", "prod"):
        rbac_path = Path("data/apiserver-kubelet-client-admin.yaml")
        if rbac_path.exists():
            try:
                subprocess.run(["kubectl", "apply", "-f", str(rbac_path)], check=True)
                log("RBAC-права для apiserver-kubelet-client применены", "ok")
            except subprocess.CalledProcessError as e:
                log(f"Ошибка при применении RBAC: {e}", "error")
        else:
            log(f"Файл {rbac_path} не найден — пропускаем применение прав", "warn")

if __name__ == "__main__":
    main()
