#!/usr/bin/env python3

"""
Initialize and configure CoreDNS using predefined YAML or Jinja2 templates.
Инициализация и настройка CoreDNS на основе YAML или Jinja2 шаблонов.
"""

import subprocess
import os
import sys
import tempfile
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log

KUBECONFIG_PATH = "/etc/kubernetes/admin.conf"

FILES = [
    ("coredns_configmap.yaml", "ConfigMap CoreDNS"),
    ("coredns_deployment.yaml", "Deployment CoreDNS"),
]

def run(cmd: list, error_msg: str, exit_on_fail=True):
    """Run a shell command and log the result."""
    try:
        subprocess.run(cmd, check=True)
        log("Успешно: " + " ".join(cmd), "ok")
    except subprocess.CalledProcessError:
        log(error_msg, "error")
        if exit_on_fail:
            sys.exit(1)

def render_template(template_path: Path) -> str:
    """Render a Jinja2 template to a temporary file and return its path."""
    env = Environment(loader=FileSystemLoader(str(template_path.parent)))
    template = env.get_template(template_path.name)
    rendered = template.render()
    with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
        tmp.write(rendered)
        return tmp.name

def apply_yaml_pair(yaml_name: str, description: str):
    """Apply either Jinja2 or raw YAML file."""
    base = Path("data/yaml") / yaml_name
    jinja = base.with_suffix(base.suffix + ".j2")

    log(f"Применение: {description}", "step")

    if jinja.exists():
        log(f"Шаблон Jinja2 найден: {jinja}", "info")
        path_to_apply = render_template(jinja)
    elif base.exists():
        log(f"YAML найден: {base}", "info")
        path_to_apply = str(base)
    else:
        log(f"Файл {yaml_name} не найден", "error")
        sys.exit(1)

    run(["kubectl", "apply", "-f", path_to_apply], f"Ошибка применения {description}")

def main():
    """Main entrypoint: installs CoreDNS and applies configs."""
    log("Экспорт KUBECONFIG", "step")
    os.environ["KUBECONFIG"] = KUBECONFIG_PATH

    log("Установка CoreDNS через kubeadm", "step")
    run(["kubeadm", "init", "phase", "addon", "coredns"], "Ошибка при установке CoreDNS")

    for yaml_name, description in FILES:
        apply_yaml_pair(yaml_name, description)

    log("Удаление pod'ов CoreDNS для перезапуска", "step")
    run(["kubectl", "delete", "pods", "-n", "kube-system", "-l", "k8s-app=kube-dns"],
        "Ошибка при удалении pod'ов CoreDNS")

    log("Вывод текущих pod'ов", "step")
    subprocess.run(["kubectl", "get", "pods", "-n", "kube-system"], check=False)

if __name__ == "__main__":
    main()
