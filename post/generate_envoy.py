# post/generate_envoy.py

"""
Configure envoy service and config from templates.
Настраивает systemd-сервис envoy и его конфигурацию из шаблонов.
"""

import os
import sys
import shutil
import filecmp
from pathlib import Path

import jinja2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log

# Пути
SERVICE_PATH = Path("/etc/systemd/system/envoy.service")
TEMPLATE_SERVICE_PATH = Path("data/systemd/envoy.service")

ENVOY_DIR = Path("/etc/envoy")
ENVOY_CONFIG_PATH = ENVOY_DIR / "envoy.yaml"
TEMPLATE_ENVOY_J2 = Path("data/yaml/envoy.yaml.j2")

# collected_info как пространство имён
import data.collected_info as collected_info


def render_template(j2_path: Path, destination: Path, context: dict) -> bool:
    """
    Render Jinja2 template with context and write to destination.
    Рендерит Jinja2-шаблон с контекстом и сохраняет в файл.
    Возвращает True, если файл изменён.
    """
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(j2_path.parent))
    template = env.get_template(j2_path.name)
    rendered = template.render(**context)

    if destination.exists() and destination.read_text() == rendered:
        return False

    destination.write_text(rendered)
    return True


def ensure_service_file():
    """
    Ensure envoy.service file exists and is up-to-date.
    Проверяет, что envoy.service существует и актуален.
    """
    if not SERVICE_PATH.exists():
        shutil.copy(TEMPLATE_SERVICE_PATH, SERVICE_PATH)
        log("Создан файл systemd: envoy.service", "ok")
        return True

    if not filecmp.cmp(SERVICE_PATH, TEMPLATE_SERVICE_PATH, shallow=False):
        shutil.copy(TEMPLATE_SERVICE_PATH, SERVICE_PATH)
        log("Обновлён файл systemd: envoy.service", "warn")
        return True

    log("Файл systemd: envoy.service актуален", "info")
    return False


def ensure_envoy_config():
    """
    Ensure /etc/envoy/envoy.yaml is created and up-to-date.
    Проверяет, что конфиг envoy существует и актуален.
    """
    ENVOY_DIR.mkdir(parents=True, exist_ok=True)

    context = {k: v for k, v in vars(collected_info).items() if not k.startswith("__")}

    changed = render_template(TEMPLATE_ENVOY_J2, ENVOY_CONFIG_PATH, context)

    if changed:
        log("Конфигурация envoy.yaml обновлена", "warn")
    else:
        log("Конфигурация envoy.yaml актуальна", "info")

    return changed


def restart_envoy():
    """
    Reload and restart envoy service.
    Перезапускает и активирует envoy.service.
    """
    os.system("systemctl daemon-reexec")
    os.system("systemctl daemon-reload")
    os.system("systemctl enable envoy")
    os.system("systemctl restart envoy")
    log("Envoy-сервис перезапущен и активирован", "ok")


def main():
    """
    Entrypoint.
    Точка входа.
    """
    log("Проверка и настройка envoy...", "info")
    service_changed = ensure_service_file()
    config_changed = ensure_envoy_config()

    if service_changed or config_changed:
        restart_envoy()
    else:
        log("Перезапуск envoy не требуется", "info")


if __name__ == "__main__":
    main()
