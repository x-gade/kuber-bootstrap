#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import json
from jinja2 import Template

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
sys.path.append(PROJECT_ROOT)

from utils.logger import log
from data.collected_info import IP

# === Константы ===
CILIUM_REPO = "https://github.com/cilium/cilium.git"
CILIUM_BRANCH = "v1.14.6"
CILIUM_DIR = "/opt/cni/cilium"
CILIUM_HELM_DIR = os.path.join(CILIUM_DIR, "install/kubernetes/cilium")
CILIUM_YAML_PATH = os.path.join(CILIUM_DIR, "install/kubernetes/cilium.yaml")
CNI_CONFIG_DIR = "/etc/cni/net.d"
TEMP_CNI_FILE = os.path.join(CNI_CONFIG_DIR, "10-bridge-temporary.conf")

def run_shell_cmd(cmd: list, cwd=None, capture=False):
    try:
        result = subprocess.run(
            cmd, check=True, cwd=cwd,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None
        )
        return result.stdout.decode().strip() if capture else 0
    except subprocess.CalledProcessError as e:
        if capture:
            return e.stderr.decode().strip()
        return 1

def ensure_cilium_repo():
    if os.path.exists(CILIUM_DIR):
        log("Папка cilium уже существует, клонирование не требуется.", "ok")
    else:
        log("Клонируем репозиторий Cilium...", "info")
        if run_shell_cmd(["git", "clone", CILIUM_REPO, CILIUM_DIR]) != 0:
            log("Ошибка при клонировании репозитория Cilium.", "error")
            sys.exit(1)

    log(f"Переключение на ветку {CILIUM_BRANCH}...", "info")
    if run_shell_cmd(["git", "checkout", CILIUM_BRANCH], cwd=CILIUM_DIR) != 0:
        log(f"Ошибка при переключении на ветку {CILIUM_BRANCH}", "error")
        sys.exit(1)

def detect_cluster_conditions():
    log("Определение условий кластера...", "info")
    try:
        result = subprocess.run(
            ["kubectl", "get", "nodes", "-o", "json"],
            check=True, capture_output=True, text=True
        )
        data = json.loads(result.stdout)
        nodes = data.get("items", [])
        if len(nodes) == 1:
            log("Обнаружена единственная нода. Включён режим совместимости single-node.", "warn")
            return {
                "REPLICAS": 1,
                "DISABLE_AFFINITY": True,
                "ENABLE_TOLERATIONS": True
            }
        else:
            log(f"Обнаружено {len(nodes)} нод(ы). Используются стандартные параметры.", "ok")
            return {
                "REPLICAS": 2,
                "DISABLE_AFFINITY": False,
                "ENABLE_TOLERATIONS": False
            }
    except Exception as e:
        log(f"Ошибка при анализе нод: {e}", "error")
        sys.exit(1)

def generate_cilium_manifest():
    values_template = os.path.join(PROJECT_ROOT, "data", "cilium_values.yaml.j2")
    values_rendered = os.path.join(PROJECT_ROOT, "data", "cilium_values.yaml")
    port = "6443"

    overrides = detect_cluster_conditions()

    with open(values_template) as f:
        tmpl = Template(f.read())

    with open(values_rendered, "w") as f:
        f.write(tmpl.render(IP=IP, PORT=port, **overrides))

    cmd = [
        "helm", "template", "cilium", CILIUM_HELM_DIR,
        "--namespace", "kube-system",
        "--values", values_rendered
    ]

    try:
        with open(CILIUM_YAML_PATH, "w") as f:
            subprocess.run(cmd, check=True, cwd=PROJECT_ROOT, stdout=f)
        log("Манифест Cilium сгенерирован из Helm.", "ok")
    except subprocess.CalledProcessError:
        log("Ошибка при генерации Helm-манифеста.", "error")
        sys.exit(1)

def check_kubelet_status():
    log("Проверка статуса kubelet после перезапуска...", "info")
    try:
        result = subprocess.run(["systemctl", "is-active", "kubelet"], check=True, stdout=subprocess.PIPE)
        status = result.stdout.decode().strip()
        if status == "active":
            log("kubelet работает нормально.", "ok")
        else:
            log(f"kubelet не в активном состоянии: {status}", "warn")
    except subprocess.CalledProcessError as e:
        log(f"kubelet не запущен! Ошибка: {e}", "error")
        sys.exit(1)

def cleanup_temporary_bridge():
    if os.path.exists(TEMP_CNI_FILE):
        log("Удаление временного CNI (bridge)...", "info")
        os.remove(TEMP_CNI_FILE)
    else:
        log("Временный bridge уже удалён или не найден", "info")

    log("Перезапуск kubelet после удаления bridge...", "info")
    subprocess.run(["systemctl", "restart", "kubelet"])
    check_kubelet_status()

def apply_cilium_manifest():
    if not os.path.exists(CILIUM_YAML_PATH):
        generate_cilium_manifest()

    log("Удаление старой установки Cilium (если есть)...", "info")
    run_shell_cmd(["kubectl", "delete", "-f", CILIUM_YAML_PATH, "--ignore-not-found"])

    log("Применение манифеста Cilium...", "info")
    if run_shell_cmd(["kubectl", "apply", "-f", CILIUM_YAML_PATH]) != 0:
        log("Не удалось применить манифест Cilium", "error")
        sys.exit(1)

def main():
    log("== Установка Cilium из исходников с удалением временной bridge-сети ==", "start")
    ensure_cilium_repo()
    apply_cilium_manifest()
    cleanup_temporary_bridge()
    log("Cilium установлен, bridge удалён. Можно продолжать установку.", "ok")

if __name__ == "__main__":
    main()
