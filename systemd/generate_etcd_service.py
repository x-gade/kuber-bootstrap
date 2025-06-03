# systemd/generate_etcd_service.py

import os
import sys
import subprocess
import shutil
import pwd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data import collected_info

ETCD_USER = "etcd"
ETCD_DATA_DIR = "/var/lib/etcd"
ETCD_CERT_DIR = "/etc/kubernetes/pki/etcd"
GLOBAL_CA_PATH = "/etc/kubernetes/pki/ca.crt"
ETCD_SERVICE_PATH = "/etc/systemd/system/etcd.service"
MANIFESTS_DIR = "/etc/kubernetes/manifests"

def remove_etcd_manifests():
    log("Поиск и удаление встроенных pod-манифестов etcd...", "info")
    if not os.path.exists(MANIFESTS_DIR):
        log(f"Каталог {MANIFESTS_DIR} не существует — пропускаю удаление манифестов", "warn")
        return
    for file in os.listdir(MANIFESTS_DIR):
        if "etcd" in file.lower():
            full_path = os.path.join(MANIFESTS_DIR, file)
            os.remove(full_path)
            log(f"Удалён манифест: {full_path}", "ok")

def ensure_user_exists():
    log("Проверка наличия пользователя 'etcd'...", "info")
    try:
        pwd.getpwnam(ETCD_USER)
        log("Пользователь 'etcd' уже существует", "ok")
    except KeyError:
        subprocess.run(["useradd", "-r", "-s", "/sbin/nologin", ETCD_USER], check=True)
        log("Пользователь 'etcd' создан", "ok")

def prepare_data_dir():
    os.makedirs(ETCD_DATA_DIR, exist_ok=True)
    shutil.chown(ETCD_DATA_DIR, user=ETCD_USER, group=ETCD_USER)
    os.chmod(ETCD_DATA_DIR, 0o700)
    log(f"Каталог данных создан и настроен: {ETCD_DATA_DIR}", "ok")

def set_cert_permissions():
    if not os.path.isdir(ETCD_CERT_DIR):
        log(f"Каталог сертификатов не найден: {ETCD_CERT_DIR}", "error")
        sys.exit(1)

    for root, _, files in os.walk(ETCD_CERT_DIR):
        for f in files:
            full_path = os.path.join(root, f)
            if f.endswith(".key"):
                os.chmod(full_path, 0o600)
            shutil.chown(full_path, user=ETCD_USER, group=ETCD_USER)

    shutil.chown(ETCD_CERT_DIR, user=ETCD_USER, group=ETCD_USER)
    log(f"Права и владельцы сертификатов настроены: {ETCD_CERT_DIR}", "ok")

def generate_unit_file():
    if os.path.exists(ETCD_SERVICE_PATH):
        log(f"Unit-файл уже существует: {ETCD_SERVICE_PATH}", "ok")
        return

    template_path = os.path.join("data", "etcd.service.template")
    if not os.path.exists(template_path):
        log(f"Шаблон unit-файла не найден: {template_path}", "error")
        sys.exit(1)

    ip = collected_info.IP
    hostname = collected_info.HOSTNAME

    with open(template_path) as f:
        content = f.read()
        content = content.replace("{IP}", ip).replace("{HOSTNAME}", hostname)

    with open(ETCD_SERVICE_PATH, "w") as f:
        f.write(content)

    log(f"Unit-файл создан из шаблона: {ETCD_SERVICE_PATH}", "ok")

def reload_and_start():
    subprocess.run(["systemctl", "daemon-reexec"], check=True)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "--now", "etcd"], check=True)
    log("etcd запущен и добавлен в автозагрузку", "ok")

def main():
    log("=== Настройка systemd-сервиса etcd ===", "info")
    remove_etcd_manifests()
    ensure_user_exists()
    prepare_data_dir()
    set_cert_permissions()
    generate_unit_file()
    reload_and_start()

if __name__ == "__main__":
    main()
