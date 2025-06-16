# systemd/generate_apiserver_service.py

'''
Генерация systemd unit-файла для kube-apiserver с использованием Jinja2-шаблона.
Generate systemd unit file for kube-apiserver using Jinja2 template.
'''

import os
import sys
import subprocess
import yaml
import urllib.request
import shutil
from pathlib import Path
from jinja2 import Template

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data import collected_info

REQUIRED_BINARIES_PATH = Path("data/required_binaries.yaml")
SERVICE_PATH = "/etc/systemd/system/kube-apiserver.service"
MANIFESTS_DIR = "/etc/kubernetes/manifests"
CERT_DIR = "/etc/kubernetes/pki"

def get_template_path(mode: str) -> Path:
    '''
    Получает путь до Jinja2-шаблона unit-файла по режиму (dev/prod).
    Returns Jinja2 template path for systemd unit based on mode.
    '''
    if mode == "dev":
        return Path("data/systemd/apiserver_dev.service.j2")
    elif mode == "prod":
        return Path("data/systemd/apiserver_prod.service.j2")
    else:
        log(f"Неизвестный режим: {mode}", "error")
        sys.exit(1)

def remove_pod_manifest():
    '''
    Удаляет старый pod-манифест apiserver, если он существует.
    Removes old pod manifest for apiserver if it exists.
    '''
    manifest_path = os.path.join(MANIFESTS_DIR, "kube-apiserver.yaml")
    if os.path.exists(manifest_path):
        os.remove(manifest_path)
        log(f"Удалён pod-манифест: {manifest_path}", "warn")

def load_required_version():
    '''
    Загружает версию и путь бинарника kube-apiserver из YAML-файла.
    Loads kube-apiserver version and binary path from YAML.
    '''
    with open(REQUIRED_BINARIES_PATH, "r") as f:
        binaries = yaml.safe_load(f)
    if "kube-apiserver" not in binaries:
        log("Отсутствует запись о kube-apiserver в required_binaries.yaml", "error")
        sys.exit(1)
    version = binaries["kube-apiserver"]["version"]
    path = binaries["kube-apiserver"]["path"]
    return version, path

def download_binary(version, path):
    '''
    Загружает бинарник kube-apiserver, если он ещё не установлен.
    Downloads kube-apiserver binary if not present.
    '''
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

def render_unit_file(template_path, binary_path):
    '''
    Рендерит unit-файл systemd для kube-apiserver из Jinja2-шаблона.
    Renders kube-apiserver systemd unit from Jinja2 template.
    '''
    with open(template_path, "r") as f:
        template = Template(f.read())

    unit_content = template.render(
        BINARY_PATH=binary_path,
        CERT_DIR=CERT_DIR,
        IP=collected_info.IP
    )

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
    '''
    Перезапускает systemd и включает kube-apiserver.
    Reloads systemd and starts kube-apiserver.
    '''
    subprocess.run(["systemctl", "daemon-reexec"], check=True)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "restart", "kube-apiserver"], check=True)
    subprocess.run(["systemctl", "enable", "kube-apiserver"], check=True)
    log("kube-apiserver перезапущен и добавлен в автозагрузку", "ok")

def apply_rbac():
    '''
    Применяет RBAC-манифест, если он существует.
    Applies RBAC manifest if available.
    '''
    rbac_path = Path("data/apiserver-kubelet-client-admin.yaml")
    if rbac_path.exists():
        try:
            subprocess.run(["kubectl", "apply", "-f", str(rbac_path)], check=True)
            log("RBAC-права для apiserver-kubelet-client применены", "ok")
        except subprocess.CalledProcessError as e:
            log(f"Ошибка при применении RBAC: {e}", "error")
    else:
        log(f"Файл {rbac_path} не найден — пропускаем применение прав", "warn")

def main():
    '''
    Точка входа. Запускает установку и настройку kube-apiserver.
    Entry point. Installs and configures kube-apiserver.
    '''
    mode = "prod"
    if len(sys.argv) > 1 and sys.argv[1] == "--mode=dev":
        mode = "dev"
    log(f"=== Настройка kube-apiserver в режиме {mode.upper()} ===", "info")

    template_path = get_template_path(mode)
    remove_pod_manifest()
    version, path = load_required_version()
    download_binary(version, path)
    render_unit_file(template_path, path)
    reload_and_start()
    apply_rbac()

if __name__ == "__main__":
    main()
