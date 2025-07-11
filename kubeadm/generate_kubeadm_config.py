"""
Generate and apply kubeadm config to Kubernetes cluster.
Генерация и применение kubeadm-конфига в кластер Kubernetes.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Добавление корня проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data import collected_info

TEMPLATE_PATH = Path("data/yaml/kubeadm-config.yaml.j2")
OUTPUT_PATH = Path("data/yaml/kubeadm-config.yaml")


def is_kubeadm_available():
    """
    Check if kubeadm binary is available in PATH.
    Проверяет наличие бинарника kubeadm в системе.
    """
    return shutil.which("kubeadm") is not None


def generate_config():
    """
    Generate kubeadm configuration YAML from Jinja2 template.
    Генерирует kubeadm-config.yaml на основе шаблона.
    """
    if not is_kubeadm_available():
        log("kubeadm не найден, пропускаю генерацию конфигурации", "error")
        return

    if collected_info.ROLE != "control-plane":
        log("kubeadm-config.yaml генерируется только на control-plane узле", "warn")
        return

    log("Генерация kubeadm-config.yaml из шаблона...", "info")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_PATH.parent)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(TEMPLATE_PATH.name)

    rendered = template.render(
        IP=collected_info.IP,
        CLUSTER_POD_CIDR=collected_info.CLUSTER_POD_CIDR,
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(rendered)

    log(f"Файл создан: {OUTPUT_PATH}", "ok")
    apply_config_map()


def extract_cluster_configuration() -> str:
    """
    Extract ClusterConfiguration block from kubeadm YAML file.
    Извлекает полный блок ClusterConfiguration, включая apiVersion и kind.
    """
    buffer = []
    in_block = False

    with open(OUTPUT_PATH, "r") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if "kind: ClusterConfiguration" in line:

            for j in range(i - 1, -1, -1):
                if "apiVersion:" in lines[j]:
                    buffer = lines[j:i+1]
                    break

            for k in range(i + 1, len(lines)):
                if lines[k].strip().startswith("kind: InitConfiguration") or lines[k].strip() == "---":
                    break
                buffer.append(lines[k])
            break

    return "".join(buffer).strip()


def apply_config_map():
    """
    Apply ConfigMap 'kubeadm-config' with ClusterConfiguration.
    Применяет конфиг как ConfigMap kubeadm-config в кластер.
    """
    log("Формирование ConfigMap kubeadm-config из ClusterConfiguration...", "info")

    cluster_config = extract_cluster_configuration()
    if not cluster_config:
        log("ClusterConfiguration не найден в файле", "error")
        return

    # Временный файл для configmap
    temp_file = Path("/tmp/kubeadm-cluster-config.yaml")
    with open(temp_file, "w") as f:
        f.write(f"apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: kubeadm-config\n  namespace: kube-system\ndata:\n  ClusterConfiguration: |\n")
        for line in cluster_config.splitlines():
            f.write(f"    {line}\n")

    try:
        subprocess.run(["kubectl", "apply", "-f", str(temp_file)], check=True)
        log("ConfigMap kubeadm-config успешно применён", "ok")
    except subprocess.CalledProcessError:
        log("Ошибка при применении ConfigMap", "error")
    finally:
        temp_file.unlink(missing_ok=True)


if __name__ == "__main__":
    generate_config()
