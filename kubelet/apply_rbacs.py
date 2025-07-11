#!/usr/bin/env python3
"""
Render and apply all RBAC-related YAML manifests using kubectl.
Генерирует шаблоны и применяет все YAML-манифесты из data/yaml/rbac через kubectl apply -f
"""

import subprocess
from pathlib import Path
import sys
import os
from jinja2 import Template

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data import collected_info

RBAC_PATH = Path("data/yaml/rbac")

TEMPLATES = {
    "kubeadm-config-access.yaml.j2": "kubeadm-config-access.yaml",
}

def render_templates():
    """
    Render all Jinja2 templates in the RBAC directory using JOIN_TOKEN.
    Генерирует все Jinja2-шаблоны RBAC, используя переменные из collected_info.py.
    """
    # Собираем все переменные из collected_info.py
    context = {
        key: value
        for key, value in vars(collected_info).items()
        if not key.startswith("__") and not callable(value)
    }

    j2_files = sorted(RBAC_PATH.glob("*.j2"))

    if not j2_files:
        log(f"Не найдено ни одного Jinja2-шаблона в {RBAC_PATH}", "warn")
        return

    for template_path in j2_files:
        output_path = template_path.with_suffix("")

        try:
            with open(template_path, "r") as f:
                tpl = Template(f.read())

            rendered = tpl.render(**context)

            with open(output_path, "w") as f:
                f.write(rendered)

            log(f"Сгенерирован {output_path.name}", "ok")

        except Exception as e:
            log(f"Ошибка при рендеринге {template_path.name}: {e}", "error")

def apply_rbac_manifests():
    """
    Apply all YAML files from RBAC_PATH using kubectl.
    Применяет все YAML-файлы в каталоге RBAC через kubectl.
    """
    if not RBAC_PATH.exists():
        log(f"Директория {RBAC_PATH} не существует", "error")
        return

    yaml_files = sorted(RBAC_PATH.glob("*.yaml"))

    if not yaml_files:
        log(f"Нет RBAC-файлов в {RBAC_PATH}", "warn")
        return

    for file in yaml_files:
        log(f"Применение: {file}", "info")
        result = subprocess.run(
            ["kubectl", "apply", "-f", str(file)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            log(result.stdout.strip(), "ok")
        else:
            log(f"[Ошибка] {file}:\n{result.stderr.strip()}", "error")
            sys.exit(result.returncode)

if __name__ == "__main__":
    render_templates()
    apply_rbac_manifests()
