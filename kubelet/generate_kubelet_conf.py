from jinja2 import Template
import socket
import os
import sys
from pathlib import Path

# Добавляем путь к корню проекта
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from utils.logger import log

TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "data/kubelet_config_template.yaml")
OUTPUT_PATH = "/var/lib/kubelet/config.yaml"
COLLECTED_INFO_PATH = os.path.join(PROJECT_ROOT, "data/collected_info.py")

def get_node_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

def load_collected_info():
    collected = {}
    with open(COLLECTED_INFO_PATH, "r") as f:
        exec(f.read(), collected)
    return collected

def generate_kubelet_config(collected):
    with open(TEMPLATE_PATH, "r") as f:
        template = Template(f.read())

    rendered = template.render(
        pod_cidr=collected.get("CLUSTER_POD_CIDR", "10.244.0.0/16"),
        node_ip=get_node_ip()
    )

    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(rendered)

    log(f"Создан kubelet config по шаблону: {OUTPUT_PATH}", "ok")

def main():
    if not os.path.exists(COLLECTED_INFO_PATH):
        log("Файл collected_info.py не найден", "error")
        sys.exit(1)
    generate_kubelet_config(load_collected_info())

if __name__ == "__main__":
    main()
