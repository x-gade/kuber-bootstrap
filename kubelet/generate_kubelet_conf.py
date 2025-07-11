"""
Generate and apply kubelet config.yaml and update corresponding ConfigMap.
Генерация и применение файла kubelet/config.yaml и обновление соответствующего ConfigMap.
"""

import socket
import os
import sys
import subprocess
import filecmp
from pathlib import Path
from jinja2 import Template

# Пути
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from utils.logger import log

TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "data/conf/var_lib_kubelet_config.conf.j2")
OUTPUT_PATH = "/var/lib/kubelet/config.yaml"
TMP_RENDERED_PATH = "/tmp/generated-kubelet-config.yaml"
COLLECTED_INFO_PATH = os.path.join(PROJECT_ROOT, "data/collected_info.py")

def get_node_ip() -> str:
    """
    Get the local node IP address.
    Получает IP-адрес текущего узла.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

def load_collected_info() -> dict:
    """
    Load collected_info.py as dictionary.
    Загружает collected_info.py как словарь.
    """
    collected = {}
    with open(COLLECTED_INFO_PATH, "r") as f:
        exec(f.read(), collected)
    return collected

def render_template(collected: dict) -> str:
    """
    Render config.yaml Jinja2 template.
    Отрисовывает шаблон config.yaml на основе collected_info.
    """
    with open(TEMPLATE_PATH, "r") as f:
        template = Template(f.read())
    return template.render(
        pod_cidr=collected.get("CLUSTER_POD_CIDR", "10.244.0.0/16"),
        node_ip=get_node_ip()
    )

def write_file(path: str, content: str):
    """
    Write string content to file, creating directory if needed.
    Записывает строку в файл, создавая директорию при необходимости.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(content)

def apply_if_changed(rendered: str) -> bool:
    """
    Write rendered content if changed compared to existing file.
    Записывает файл только при отличии от существующего.
    """
    if os.path.exists(OUTPUT_PATH):
        write_file(TMP_RENDERED_PATH, rendered)
        if filecmp.cmp(TMP_RENDERED_PATH, OUTPUT_PATH, shallow=False):
            log("Файл config.yaml актуален — изменений нет", "info")
            os.remove(TMP_RENDERED_PATH)
            return False
        else:
            log("Файл config.yaml отличается — обновление...", "info")
            os.remove(TMP_RENDERED_PATH)

    write_file(OUTPUT_PATH, rendered)
    log(f"Обновлён kubelet config: {OUTPUT_PATH}", "ok")
    return True

def update_configmap():
    """
    Replace existing kubelet-config ConfigMap with updated content.
    Обновляет ConfigMap kubelet-config в пространстве kube-system.
    """
    try:
        subprocess.run([
            "kubectl", "-n", "kube-system", "delete", "configmap", "kubelet-config"
        ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        subprocess.run([
            "kubectl", "-n", "kube-system", "create", "configmap", "kubelet-config",
            f"--from-file=kubelet={OUTPUT_PATH}"
        ], check=True)

        log("ConfigMap kubelet-config успешно создан", "ok")
    except subprocess.CalledProcessError as e:
        log(f"Ошибка при создании configmap kubelet-config: {e}", "error")
        sys.exit(1)

def main():
    """
    Entrypoint: generate config, apply if changed, update ConfigMap.
    Точка входа: генерирует конфиг, применяет при изменении, обновляет ConfigMap.
    """
    if not os.path.exists(COLLECTED_INFO_PATH):
        log("Файл collected_info.py не найден", "error")
        sys.exit(1)

    collected = load_collected_info()
    rendered = render_template(collected)

    changed = apply_if_changed(rendered)
    if changed:
        update_configmap()
    else:
        log("Пропуск создания configmap — файл без изменений", "info")

if __name__ == "__main__":
    main()
