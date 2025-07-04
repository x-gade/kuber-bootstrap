#!/usr/bin/env python3
"""
Установка бинарника cilium-agent и генерация systemd unit-файла
для запуска его как systemd-сервиса с шаблонизацией через Jinja2.
"""

import os
import sys
import tarfile
import shutil
import subprocess
import hashlib
from pathlib import Path
from jinja2 import Template

# Добавляем путь до корня проекта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data import collected_info

# Пути
ARCHIVE_PATH = Path("/opt/kuber-bootstrap/binares/cilium.tar.gz")
EXTRACT_DIR = Path("/opt/kuber-bootstrap/tmp/cilium_extract")
TARGET_BIN = Path("/usr/local/bin/cilium-agent")
CONFIG_DIR = Path("/etc/cilium")
CONFIG_TEMPLATE_PATH = Path("data/yaml/cilium.yaml.j2")
CONFIG_OUTPUT_PATH = CONFIG_DIR / "cilium.yaml"
TEMPLATE_PATH = Path("data/systemd/cilium.service.j2")
SERVICE_PATH = Path("/etc/systemd/system/cilium.service")

# Флаги обновления
SERVICE_UPDATED = False
BINARY_UPDATED = False

def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def ensure_directories():
    for path in [TARGET_BIN.parent, CONFIG_DIR]:
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            log(f"Создана директория: {path}", "ok")
        else:
            log(f"Директория уже существует: {path}", "info")

def extract_and_install():
    global BINARY_UPDATED

    if not ARCHIVE_PATH.exists():
        log(f"Архив не найден: {ARCHIVE_PATH}", "error")
        sys.exit(1)

    if EXTRACT_DIR.exists():
        shutil.rmtree(EXTRACT_DIR)
    EXTRACT_DIR.mkdir(parents=True)

    log(f"Распаковка архива {ARCHIVE_PATH} в {EXTRACT_DIR}", "info")
    with tarfile.open(ARCHIVE_PATH, "r:gz") as tar:
        tar.extractall(path=EXTRACT_DIR)

    source = EXTRACT_DIR / "daemon" / "cilium-agent"
    if not source.exists():
        log("Бинарник cilium-agent не найден после распаковки", "error")
        sys.exit(1)

    if TARGET_BIN.exists() and file_sha256(source) == file_sha256(TARGET_BIN):
        log("Бинарник не изменился — замена не требуется", "info")
    else:
        if TARGET_BIN.exists():
            subprocess.run(["systemctl", "stop", "cilium.service"], check=False)
            log("Старый бинарник остановлен перед заменой", "warn")

        shutil.copy2(source, TARGET_BIN)
        os.chmod(TARGET_BIN, 0o755)
        log(f"Бинарник установлен: {TARGET_BIN}", "ok")
        BINARY_UPDATED = True

    shutil.rmtree(EXTRACT_DIR, ignore_errors=True)
    log("Временные файлы удалены", "info")

def render_config_file():
    """
    Генерирует YAML-конфиг для cilium-agent из Jinja2 шаблона
    """
    if not CONFIG_TEMPLATE_PATH.exists():
        log(f"Шаблон конфига не найден: {CONFIG_TEMPLATE_PATH}", "error")
        sys.exit(1)

    with open(CONFIG_TEMPLATE_PATH, "r") as f:
        template = Template(f.read())

    rendered = template.render(
        HOSTNAME=collected_info.HOSTNAME,
        IP=collected_info.IP,
        POD_CIDR=collected_info.CLUSTER_POD_CIDR,
        CLUSTER_POD_CIDR=collected_info.CLUSTER_POD_CIDR,
        CIDR=collected_info.CIDR
    )

    if CONFIG_OUTPUT_PATH.exists():
        current = CONFIG_OUTPUT_PATH.read_text()
        if current == rendered:
            log("YAML-конфиг актуален — не изменён", "info")
            return

        backup = CONFIG_OUTPUT_PATH.with_suffix(".bak")
        shutil.copy(CONFIG_OUTPUT_PATH, backup)
        log(f"Резервная копия старого YAML: {backup}", "warn")

    CONFIG_OUTPUT_PATH.write_text(rendered)
    log(f"Конфиг cilium.yaml обновлён: {CONFIG_OUTPUT_PATH}", "ok")

def render_unit_file():
    global SERVICE_UPDATED

    with open(TEMPLATE_PATH, "r") as f:
        template = Template(f.read())

    rendered = template.render(
        BINARY_PATH=TARGET_BIN,
        CONFIG_DIR=CONFIG_DIR,
        IP=collected_info.IP,
        POD_CIDR=collected_info.CLUSTER_POD_CIDR
    )

    if SERVICE_PATH.exists():
        current = SERVICE_PATH.read_text()
        if current == rendered:
            log("Unit-файл актуален — принудительный перезапуск", "warn")
            return

        backup = SERVICE_PATH.with_suffix(".bak")
        shutil.copy(SERVICE_PATH, backup)
        log(f"Старый unit-файл сохранён: {backup}", "warn")

    SERVICE_PATH.write_text(rendered)
    SERVICE_UPDATED = True
    log(f"Unit-файл обновлён: {SERVICE_PATH}", "ok")

def reload_and_start():
    if not (SERVICE_UPDATED or BINARY_UPDATED):
        log("Нет изменений — пропускаем перезапуск systemd", "info")
        return

    subprocess.run(["systemctl", "daemon-reexec"], check=True)
    subprocess.run(["systemctl", "daemon-reload"], check=True)

    # Убедиться, что verify_bpf_mount исполнимый
    if not os.access("/opt/kuber-bootstrap/post/verify_bpf_mount.py", os.X_OK):
        os.chmod("/opt/kuber-bootstrap/post/verify_bpf_mount.py", 0o755)
        log("[AUTO] Установлен +x на verify_bpf_mount.py", "warn")

    # Отображаем статус и последние логи, если рестарт неудачен
    try:
        subprocess.run(["systemctl", "restart", "cilium"], check=True)
    except subprocess.CalledProcessError:
        log("Ошибка запуска сервиса Cilium", "error")
        subprocess.run(["systemctl", "status", "cilium.service"])
        subprocess.run(["journalctl", "-xeu", "cilium.service", "--no-pager"])
        raise

    subprocess.run(["systemctl", "enable", "cilium"], check=True)
    log("Сервис cilium запущен и добавлен в автозагрузку", "ok")

def main():
    log("=== Установка cilium-agent и генерация systemd ===", "info")
    ensure_directories()
    extract_and_install()
    render_config_file()
    render_unit_file()
    reload_and_start()

if __name__ == "__main__":
    main()
