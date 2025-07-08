"""
Kubelet configuration generator with role-specific templates.

Генератор конфигурации kubelet с использованием разных шаблонов
для control-plane и worker узлов. Выбор шаблона зависит от
флага командной строки: `-cp` или `-w`.
"""

from jinja2 import Template
import socket
import os
import sys
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from utils.logger import log

COLLECTED_INFO_PATH = os.path.join(PROJECT_ROOT, "data/collected_info.py")
OUTPUT_PATH = "/var/lib/kubelet/config.yaml"

TEMPLATE_CP = os.path.join(PROJECT_ROOT, "data/yaml/kubelet_config_control_plane.yaml")
TEMPLATE_WK = os.path.join(PROJECT_ROOT, "data/yaml/kubelet_config_worker.yaml")

def get_node_ip():
    """
    Get the current node's primary IP address.
    Получает IP-адрес текущего узла.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

def load_collected_info():
    """
    Load node metadata from collected_info.py.
    Загружает информацию об узле из файла collected_info.py.
    """
    collected = {}
    with open(COLLECTED_INFO_PATH, "r") as f:
        exec(f.read(), collected)
    return collected

def generate_kubelet_config(template_path, collected):
    """
    Render and write kubelet config from Jinja2 template.
    
    Генерирует конфигурационный файл kubelet из шаблона Jinja2
    и сохраняет его в /var/lib/kubelet/config.yaml.
    """
    if not os.path.exists(template_path):
        log(f"Шаблон не найден: {template_path}", "error")
        sys.exit(1)

    with open(template_path, "r") as f:
        template = Template(f.read())

    rendered = template.render(
        pod_cidr=collected.get("CLUSTER_POD_CIDR", "10.244.0.0/16"),
        node_ip=get_node_ip()
    )

    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(rendered)

    log(f"Создан kubelet config по шаблону: {template_path}", "ok")

def main():
    """
    Entry point. Detects node role and renders appropriate kubelet config.
    
    Точка входа. Определяет роль узла (worker или control-plane)
    и генерирует соответствующий конфигурационный файл kubelet.
    """
    if not os.path.exists(COLLECTED_INFO_PATH):
        log("Файл collected_info.py не найден", "error")
        sys.exit(1)

    if len(sys.argv) != 2 or sys.argv[1] not in ["-cp", "-w"]:
        log("Укажи флаг роли: -cp (control-plane) или -w (worker)", "error")
        sys.exit(1)

    collected = load_collected_info()
    role_flag = sys.argv[1]

    if role_flag == "-cp":
        generate_kubelet_config(TEMPLATE_CP, collected)
    elif role_flag == "-w":
        generate_kubelet_config(TEMPLATE_WK, collected)

if __name__ == "__main__":
    main()
