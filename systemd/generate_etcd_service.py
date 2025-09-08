#!/usr/bin/env python3
"""
Generate and enable systemd unit for etcd from Jinja2 template.
Создаёт и активирует systemd unit-файл etcd на основе Jinja2-шаблона.
"""

import os
import sys
import subprocess
import shutil
import pwd
from jinja2 import Template

# Добавляем корень проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data import collected_info

# === Константы ===
ETCD_USER = "etcd"
ETCD_DATA_DIR = "/var/lib/etcd"
ETCD_CERT_DIR = "/etc/kubernetes/pki/etcd"
GLOBAL_CA_PATH = "/etc/kubernetes/pki/ca.crt"
ETCD_SERVICE_PATH = "/etc/systemd/system/etcd.service"
MANIFESTS_DIR = "/etc/kubernetes/manifests"
TEMPLATE_PATH = os.path.join("data", "systemd", "etcd.service.j2")

def remove_etcd_manifests():
    """
    Remove static pod manifests for etcd if they exist.
    Удаляет статические pod-манифесты etcd, если они есть.
    """
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
    """
    Ensure the etcd system user exists, or create it.
    Проверяет наличие системного пользователя etcd, создаёт при необходимости.
    """
    log("Проверка наличия пользователя 'etcd'...", "info")
    try:
        pwd.getpwnam(ETCD_USER)
        log("Пользователь 'etcd' уже существует", "ok")
    except KeyError:
        subprocess.run(["useradd", "-r", "-s", "/sbin/nologin", ETCD_USER], check=True)
        log("Пользователь 'etcd' создан", "ok")

def prepare_data_dir():
    """
    Create and set permissions for etcd data directory.
    Создаёт и настраивает права на каталог данных etcd.
    """
    os.makedirs(ETCD_DATA_DIR, exist_ok=True)
    shutil.chown(ETCD_DATA_DIR, user=ETCD_USER, group=ETCD_USER)
    os.chmod(ETCD_DATA_DIR, 0o700)
    log(f"Каталог данных создан и настроен: {ETCD_DATA_DIR}", "ok")

def set_cert_permissions():
    """
    Ensure certificate files have proper ownership and permissions.
    Настраивает владельцев и права доступа на сертификаты etcd.
    """
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
    """
    Render and write etcd systemd unit file from Jinja2 template.
    Генерирует и сохраняет systemd unit-файл etcd из Jinja2-шаблона.
    """
    if os.path.exists(ETCD_SERVICE_PATH):
        log(f"Unit-файл уже существует: {ETCD_SERVICE_PATH}", "ok")
        return

    if not os.path.exists(TEMPLATE_PATH):
        log(f"Шаблон unit-файла не найден: {TEMPLATE_PATH}", "error")
        sys.exit(1)

    ip = collected_info.IP
    hostname = collected_info.HOSTNAME

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = Template(f.read())
        rendered = template.render(IP=ip, HOSTNAME=hostname)

    with open(ETCD_SERVICE_PATH, "w", encoding="utf-8") as f:
        f.write(rendered)

    log(f"Unit-файл создан из шаблона: {ETCD_SERVICE_PATH}", "ok")

def reload_and_start():
    """
    Reload systemd, enable and start etcd service.
    Перезагружает systemd, активирует и запускает etcd.
    """
    subprocess.run(["systemctl", "daemon-reexec"], check=True)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "--now", "etcd"], check=True)
    log("etcd запущен и добавлен в автозагрузку", "ok")

def main():
    """
    Entry point for etcd service setup.
    Точка входа для настройки и запуска systemd-сервиса etcd.
    """
    log("=== Настройка systemd-сервиса etcd ===", "info")
    remove_etcd_manifests()
    ensure_user_exists()
    prepare_data_dir()
    set_cert_permissions()
    generate_unit_file()
    reload_and_start()

if __name__ == "__main__":
    main()
