# systemd/generate_kubelet_service.py

'''
Генерация systemd unit-файла для kubelet с использованием Jinja2-шаблона.
Добавляет проверку и настройку containerd для корректной работы CNI.
Generate systemd unit file for kubelet using Jinja2 template.
Also prepares containerd config for CNI.
'''

import os
import sys
import subprocess
import yaml
import shutil
from pathlib import Path
from jinja2 import Template

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data import collected_info

REQUIRED_BINARIES_PATH = Path("data/required_binaries.yaml")
SERVICE_PATH = "/lib/systemd/system/kubelet.service"
TEMPLATE_PATH = Path("data/systemd/kubelet.service.j2")
CONTAINERD_CONFIG_PATH = "/etc/containerd/config.toml"

def load_required_version():
    '''
    Загружает версию и путь бинарника kubelet из YAML-файла.
    Loads kubelet version and binary path from YAML.
    '''
    with open(REQUIRED_BINARIES_PATH, "r") as f:
        binaries = yaml.safe_load(f)
    if "kubelet" not in binaries:
        log("Отсутствует запись о kubelet в required_binaries.yaml", "error")
        sys.exit(1)
    version = binaries["kubelet"]["version"]
    path = binaries["kubelet"]["path"]
    return version, path

def download_binary(version, path):
    '''
    Загружает бинарник kubelet, если он ещё не установлен.
    Downloads kubelet binary if not present.
    '''
    if os.path.exists(path):
        log(f"Бинарник уже установлен: {path}", "ok")
        return

    url = f"https://dl.k8s.io/release/{version}/bin/linux/amd64/kubelet"
    log(f"Скачивание kubelet {version} из {url}...", "info")
    try:
        import urllib.request
        urllib.request.urlretrieve(url, path)
        os.chmod(path, 0o755)
        log(f"Бинарник установлен в: {path}", "ok")
    except Exception as e:
        log(f"Ошибка при скачивании kubelet: {e}", "error")
        sys.exit(1)

def ensure_containerd_config():
    '''
    Проверяет наличие /etc/containerd/config.toml.
    Если отсутствует – создаёт директорию, генерирует дефолтный конфиг и перезапускает containerd.
    Checks /etc/containerd/config.toml. If missing – creates default config and restarts containerd.
    '''
    if os.path.exists(CONTAINERD_CONFIG_PATH):
        log("Конфиг containerd уже существует – пропускаем генерацию", "ok")
        return

    log("Создание дефолтного containerd config.toml...", "info")

    # Создаём папку, если её нет
    os.makedirs("/etc/containerd", exist_ok=True)

    try:
        # Генерируем дефолтный конфиг
        result = subprocess.run(
            ["containerd", "config", "default"],
            capture_output=True,
            text=True,
            check=True
        )
        with open(CONTAINERD_CONFIG_PATH, "w") as f:
            f.write(result.stdout)
        log(f"containerd config.toml создан: {CONTAINERD_CONFIG_PATH}", "ok")
    except subprocess.CalledProcessError as e:
        log(f"Не удалось сгенерировать containerd config: {e.stderr}", "error")
        sys.exit(1)

    # Перезапускаем containerd с новым конфигом
    subprocess.run(["systemctl", "restart", "containerd"], check=True)
    log("containerd перезапущен с новым конфигом", "ok")

def render_unit_file(template_path, binary_path):
    '''
    Рендерит unit-файл systemd для kubelet из шаблона.
    Renders kubelet systemd unit from template.
    '''
    with open(template_path, "r") as f:
        template = Template(f.read())

    unit_content = template.render(
        BINARY_PATH=binary_path,
    )

    changed = True
    if os.path.exists(SERVICE_PATH):
        with open(SERVICE_PATH, "r") as f:
            current_content = f.read()
        if current_content == unit_content:
            log("Unit-файл уже актуален, но будет выполнен перезапуск", "warn")
            changed = False
        else:
            backup_path = SERVICE_PATH + ".bak"
            shutil.copy(SERVICE_PATH, backup_path)
            log(f"Создана резервная копия: {backup_path}", "warn")

    with open(SERVICE_PATH, "w") as f:
        f.write(unit_content)
    if changed:
        log(f"Unit-файл обновлён: {SERVICE_PATH}", "ok")

def reload_and_start():
    '''
    Перезапускает systemd и включает kubelet.
    Reloads systemd and starts kubelet.
    '''
    subprocess.run(["systemctl", "daemon-reexec"], check=True)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "restart", "kubelet"], check=True)
    subprocess.run(["systemctl", "enable", "kubelet"], check=True)
    log("kubelet перезапущен и добавлен в автозагрузку", "ok")

def main():
    '''
    Точка входа. Запускает установку и настройку kubelet.
    Entry point. Installs and configures kubelet.
    '''
    log("=== Настройка containerd + kubelet ===", "info")

    # Сначала убедимся, что containerd настроен для CNI
    ensure_containerd_config()

    # Потом уже устанавливаем kubelet
    version, path = load_required_version()
    download_binary(version, path)
    render_unit_file(TEMPLATE_PATH, path)
    reload_and_start()

if __name__ == "__main__":
    main()
