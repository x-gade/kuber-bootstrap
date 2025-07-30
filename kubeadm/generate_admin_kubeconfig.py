#!/usr/bin/env python3
"""
Generate and apply kubeconfig for admin user in different modes.
Генерация и применение kubeconfig для пользователя admin в разных режимах.
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, meta

# Подключаем логгер
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log

# Пути к шаблонам
CP_TEMPLATE_PATH = Path("data/conf/admin.conf.j2")              # шаблон для control-plane
WORKER_TEMPLATE_PATH = Path("data/conf/admin_worker.conf.j2")  # шаблон для worker

# Пути для итогового kubeconfig
KUBECONFIG_PATH = Path("/etc/kubernetes/admin.conf")
PROFILE_EXPORT_PATH = Path("/etc/profile.d/set-kubeconfig.sh")

# Данные для control-plane
from data import collected_info

# Данные для worker
JOIN_INFO_PATH = Path("data/join_info.json")


def get_template_context_cp(template_path: Path) -> dict:
    """
    Extract variables from control-plane template and populate from collected_info.py.
    Извлекает переменные из шаблона control-plane и заполняет их из collected_info.py.
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
            log(f"Variable `{var}` is missing in collected_info.py / Переменная `{var}` отсутствует в collected_info.py", "error")
            sys.exit(1)
    return context


def get_template_context_worker(template_path: Path) -> dict:
    """
    Extract required data for worker kubeconfig from join_info.json.
    Извлекает необходимые данные для worker kubeconfig из join_info.json.
    """
    if not JOIN_INFO_PATH.exists():
        log(f"File {JOIN_INFO_PATH} not found! Run collecter_join_info.py on worker first. / Файл {JOIN_INFO_PATH} не найден! Сначала запусти collecter_join_info.py на воркере.", "error")
        sys.exit(1)

    with open(JOIN_INFO_PATH, "r", encoding="utf-8") as f:
        join_data = json.load(f)

    required_keys = ["CONTROL_PLANE_IP", "CILIUM_TOKEN"]
    for k in required_keys:
        if k not in join_data:
            log(f"Missing key `{k}` in join_info.json! / Отсутствует ключ `{k}` в join_info.json!", "error")
            sys.exit(1)

    return {
        "CONTROL_PLANE_IP": join_data["CONTROL_PLANE_IP"],
        "CILIUM_TOKEN": join_data["CILIUM_TOKEN"]
    }


def render_template(template_path: Path, context: dict) -> str:
    """
    Render Jinja2 template with provided context.
    Отрисовывает шаблон Jinja2 с переданным контекстом.
    """
    env = Environment(loader=FileSystemLoader(template_path.parent))
    template = env.get_template(template_path.name)
    return template.render(context)


def files_differ(path1: Path, path2_content: str) -> bool:
    """
    Compare file content with new rendered content.
    Сравнивает содержимое существующего файла с новым сгенерированным текстом.
    """
    if not path1.exists():
        return True
    with open(path1, "r") as f:
        existing = f.read()
    return hashlib.sha256(existing.encode()) != hashlib.sha256(path2_content.encode())


def write_kubeconfig(content: str):
    """
    Write kubeconfig file and configure KUBECONFIG export.
    Записывает kubeconfig и настраивает экспорт переменной окружения.
    """
    KUBECONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(KUBECONFIG_PATH, "w") as f:
        f.write(content)
    log(f"Kubeconfig saved: {KUBECONFIG_PATH} / Kubeconfig сохранён: {KUBECONFIG_PATH}", "ok")

    with open(PROFILE_EXPORT_PATH, "w") as f:
        f.write(f'export KUBECONFIG={KUBECONFIG_PATH}\n')
    log(f"KUBECONFIG export added to: {PROFILE_EXPORT_PATH} / Экспорт переменной KUBECONFIG добавлен в: {PROFILE_EXPORT_PATH}", "ok")


def generate_kubeconfig(mode: str):
    """
    Generate kubeconfig depending on the selected mode.
    Генерирует kubeconfig в зависимости от выбранного режима.

    Modes / Режимы:
    -cpb → control-plane (admin.conf for full cluster access)
           control-plane (admin.conf для полного доступа к кластеру)
    -w   → worker (admin.conf with Cilium token for limited access)
           worker (admin.conf с токеном Cilium для ограниченного доступа)
    """
    if mode == "-cpb":
        log("Generating admin.conf for control-plane... / Генерация admin.conf для control-plane...", "info")
        template = CP_TEMPLATE_PATH
        context = get_template_context_cp(template)

    elif mode == "-w":
        log("Generating admin.conf for worker (using join_info.json)... / Генерация admin.conf для worker (по join_info.json)...", "info")
        template = WORKER_TEMPLATE_PATH
        context = get_template_context_worker(template)

    else:
        log("Usage: python3 generate_admin_kubeconfig.py -cpb | -w / Использование: python3 generate_admin_kubeconfig.py -cpb | -w", "error")
        sys.exit(1)

    rendered = render_template(template, context)

    if not KUBECONFIG_PATH.exists():
        log("kubeconfig not found, creating... / kubeconfig не найден, создаю...", "warn")
        write_kubeconfig(rendered)
    elif files_differ(KUBECONFIG_PATH, rendered):
        log("kubeconfig differs, updating... / Обнаружены изменения, обновляю файл...", "warn")
        write_kubeconfig(rendered)
    else:
        log("kubeconfig already up-to-date, skipping / kubeconfig уже актуален, пропускаю", "ok")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        log("Usage: python3 generate_admin_kubeconfig.py -cpb | -w / Использование: python3 generate_admin_kubeconfig.py -cpb | -w", "error")
        sys.exit(1)

    mode = sys.argv[1]
    generate_kubeconfig(mode)
