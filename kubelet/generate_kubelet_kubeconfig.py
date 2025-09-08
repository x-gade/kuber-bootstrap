# kubelet/generate_kubelet_kubeconfig.py

"""
Generate and apply kubelet kubeconfig from template.
Генерация и применение kubeconfig для kubelet из шаблона.
"""

import os
import sys
import hashlib
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log
from data import collected_info

TEMPLATE_PATH = Path("data/conf/kubelet.conf.j2")
KUBECONFIG_PATH = Path("/etc/kubernetes/kubelet.conf")


def render_template(template_path: Path, context: dict) -> str:
    """
    Render Jinja2 template with context.
    Отрисовывает шаблон Jinja2 с переданным контекстом.
    """
    env = Environment(loader=FileSystemLoader(template_path.parent))
    template = env.get_template(template_path.name)
    return template.render(context)


def files_differ(target_path: Path, new_content: str) -> bool:
    """
    Compare existing file with rendered content.
    Сравнивает существующий файл с отрендеренным содержимым.
    """
    if not target_path.exists():
        return True
    with open(target_path, "r") as f:
        current = f.read()
    return hashlib.sha256(current.encode()) != hashlib.sha256(new_content.encode())


def write_kubeconfig(content: str):
    """
    Write rendered kubeconfig to file.
    Записывает отрендеренный kubeconfig в файл.
    """
    KUBECONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(KUBECONFIG_PATH, "w") as f:
        f.write(content)
    log(f"Kubelet kubeconfig записан: {KUBECONFIG_PATH}", "ok")


def generate_kubelet_kubeconfig():
    """
    Main entry: generate kubelet.conf from template and apply if changed.
    Основная точка входа: генерация kubelet.conf из шаблона и применение при изменениях.
    """
    log("Генерация kubelet kubeconfig...", "step")

    if not hasattr(collected_info, "IP"):
        log("Не найден параметр `IP` в collected_info.py", "error")
        sys.exit(1)

    rendered = render_template(TEMPLATE_PATH, {"IP": collected_info.IP})

    if not KUBECONFIG_PATH.exists():
        log("Файл kubelet.conf отсутствует, создаю...", "warn")
        write_kubeconfig(rendered)
    elif files_differ(KUBECONFIG_PATH, rendered):
        log("Обнаружены изменения в kubelet.conf, обновляю...", "warn")
        write_kubeconfig(rendered)
    else:
        log("Файл kubelet.conf актуален, пропускаю", "ok")


if __name__ == "__main__":
    generate_kubelet_kubeconfig()
