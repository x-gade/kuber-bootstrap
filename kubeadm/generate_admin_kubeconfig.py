# kubeadm/generate_admin_kubeconfig.py

"""
Generate and apply kubeconfig for admin user.
Генерация и применение kubeconfig для пользователя admin.
"""

import os
import sys
import yaml
import hashlib
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pathlib import Path
from jinja2 import Environment, FileSystemLoader, meta
from utils.logger import log
from data import collected_info

TEMPLATE_PATH = Path("data/conf/admin.conf.j2")
KUBECONFIG_PATH = Path("/etc/kubernetes/admin.conf")
PROFILE_EXPORT_PATH = Path("/etc/profile.d/set-kubeconfig.sh")


def get_template_context(template_path: Path) -> dict:
    """
    Extract used variables from Jinja2 template and fetch their values from collected_info.
    Извлекает переменные из шаблона Jinja2 и получает их значения из collected_info.
    """
    env = Environment(loader=FileSystemLoader(template_path.parent))
    source = template_path.read_text()
    parsed_content = env.parse(source)
    required_vars = meta.find_undeclared_variables(parsed_content)

    context = {}
    for var in required_vars:
        if hasattr(collected_info, var):
            context[var] = getattr(collected_info, var)
        else:
            log(f"Переменная `{var}` отсутствует в collected_info.py", "error")
            sys.exit(1)
    return context


def render_template(template_path: Path, context: dict) -> str:
    """
    Render Jinja2 template with context.
    Отрисовывает шаблон Jinja2 с переданным контекстом.
    """
    env = Environment(loader=FileSystemLoader(template_path.parent))
    template = env.get_template(template_path.name)
    return template.render(context)


def files_differ(path1: Path, path2_content: str) -> bool:
    """
    Compare file content with string content.
    Сравнивает содержимое файла с переданной строкой.
    """
    if not path1.exists():
        return True
    with open(path1, "r") as f:
        existing = f.read()
    return hashlib.sha256(existing.encode()) != hashlib.sha256(path2_content.encode())


def write_kubeconfig(content: str):
    """
    Write kubeconfig file and set KUBECONFIG export.
    Записывает kubeconfig и устанавливает переменную окружения.
    """
    KUBECONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(KUBECONFIG_PATH, "w") as f:
        f.write(content)
    log(f"Kubeconfig сохранён: {KUBECONFIG_PATH}", "ok")

    with open(PROFILE_EXPORT_PATH, "w") as f:
        f.write(f'export KUBECONFIG={KUBECONFIG_PATH}\n')
    log(f"Экспорт переменной KUBECONFIG добавлен в: {PROFILE_EXPORT_PATH}", "ok")


def generate_admin_kubeconfig():
    """
    Generate kubeconfig from template and apply if changed.
    Генерирует kubeconfig из шаблона и применяет при изменении.
    """
    log("Проверка и генерация admin.kubeconfig...", "info")

    context = get_template_context(TEMPLATE_PATH)
    rendered = render_template(TEMPLATE_PATH, context)

    if not KUBECONFIG_PATH.exists():
        log("Файл kubeconfig отсутствует, создаю...", "warn")
        write_kubeconfig(rendered)
    elif files_differ(KUBECONFIG_PATH, rendered):
        log("Обнаружены изменения в kubeconfig, обновляю файл...", "warn")
        write_kubeconfig(rendered)
    else:
        log("Файл kubeconfig уже актуален, пропускаю", "ok")


if __name__ == "__main__":
    generate_admin_kubeconfig()
