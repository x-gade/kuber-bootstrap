#!/usr/bin/env python3
"""
Установка Cilium и применение CNI-манифеста.
Install Cilium and apply the CNI manifest.
"""

import os
import sys
import subprocess
import shutil
import json
import time
from jinja2 import Template

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
sys.path.append(PROJECT_ROOT)

from utils.logger import log
from data.collected_info import IP, CLUSTER_POD_CIDR

# === Константы / Constants ===
CILIUM_REPO = "https://github.com/cilium/cilium.git"
CILIUM_BRANCH = "v1.14.6"
CILIUM_DIR = "/opt/cni/cilium"
CILIUM_HELM_DIR = os.path.join(CILIUM_DIR, "install/kubernetes/cilium")
CILIUM_YAML_PATH = os.path.join(CILIUM_DIR, "install/kubernetes/cilium.yaml")
CILIUM_VALUES_RENDERED = os.path.join(PROJECT_ROOT, "data", "cni", "cilium_values.yaml")
CNI_CONFIG_DIR = "/etc/cni/net.d"
TEMP_CNI_FILE = os.path.join(CNI_CONFIG_DIR, "10-bridge-temporary.conf")

def run_shell_cmd(cmd: list, cwd=None, capture=False):
    """
    Запускает shell-команду и возвращает результат.
    Run a shell command and return the result.
    """

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
    """
    Клонирует репозиторий Cilium и переключается на нужную ветку.
    Clone the Cilium repo and checkout the desired branch.
    """

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
    """
    Определяет параметры установки в зависимости от числа нод.
    Detects cluster conditions and sets install parameters based on node count.
    """

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

def patch_custom_cni_conf():
    """
    Устанавливает custom-cni-conf=true в configmap cilium-config.
    Sets custom-cni-conf=true in the cilium-config ConfigMap.
    """
    log("Проверка и патч ConfigMap cilium-config (custom-cni-conf=true)...", "info")
    try:
        subprocess.run([
            "kubectl", "patch", "configmap", "cilium-config",
            "-n", "kube-system",
            "--type", "merge",
            "-p", '{"data":{"custom-cni-conf":"true"}}'
        ], check=True)
        log("ConfigMap cilium-config успешно обновлён.", "ok")
    except subprocess.CalledProcessError:
        log("Не удалось обновить ConfigMap cilium-config!", "error")
        sys.exit(1)

def generate_cilium_manifest():
    """
    Генерирует Helm-манифест Cilium и сохраняет его.
    Render Cilium Helm manifest and save it to file.
    """
    log("Генерация Helm-манифеста Cilium...", "info")

    values_template = os.path.join(PROJECT_ROOT, "data", "cni", "cilium_values.yaml.j2")
    port = "6443"

    if not CLUSTER_POD_CIDR:
        log("CLUSTER_POD_CIDR не задан — невозможна генерация Cilium-манифеста", "error")
        sys.exit(1)

    overrides = detect_cluster_conditions()

    context = {
        "IP": IP,
        "PORT": port,
        "CLUSTER_POD_CIDR": CLUSTER_POD_CIDR,
        "REPLICAS": int(overrides["REPLICAS"]),
        "DISABLE_AFFINITY": bool(overrides["DISABLE_AFFINITY"]),
        "ENABLE_TOLERATIONS": bool(overrides["ENABLE_TOLERATIONS"]),
    }

    try:
        with open(values_template) as f:
            tmpl = Template(f.read())
        rendered_values = tmpl.render(**context)
    except Exception as e:
        log(f"Ошибка при рендере шаблона values-файла: {e}", "error")
        sys.exit(1)

    with open(CILIUM_VALUES_RENDERED, "w") as f:
        f.write(rendered_values)
    log(f"Сгенерирован values-файл: {CILIUM_VALUES_RENDERED}", "ok")

    cmd = [
        "helm", "template", "cilium", CILIUM_HELM_DIR,
        "--namespace", "kube-system",
        "--values", CILIUM_VALUES_RENDERED,
        "--include-crds",
        "--set", "crd.annotations="
    ]

    try:
        with open(CILIUM_YAML_PATH, "w") as f:
            subprocess.run(cmd, check=True, cwd=PROJECT_ROOT, stdout=f)
        log("Манифест Cilium сгенерирован из Helm.", "ok")
    except subprocess.CalledProcessError:
        log("Ошибка при генерации Helm-манифеста.", "error")
        sys.exit(1)

def check_kubelet_status():
    """
    Проверяет состояние kubelet после перезапуска.
    Check the kubelet service status after restart.
    """

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
    """
    Удаляет временный CNI-мост и перезапускает kubelet.
    Delete temporary bridge CNI config and restart kubelet.
    """

    if os.path.exists(TEMP_CNI_FILE):
        log("Удаление временного CNI (bridge)...", "info")
        os.remove(TEMP_CNI_FILE)
    else:
        log("Временный bridge уже удалён или не найден", "info")

    log("Перезапуск kubelet после удаления bridge...", "info")
    subprocess.run(["systemctl", "restart", "kubelet"])
    check_kubelet_status()

def apply_sysctl_settings():
    """
    Настраивает и сохраняет параметры sysctl для Cilium.
    Configure and persist sysctl settings required by Cilium.
    """

    log("Настройка sysctl параметров для Cilium...", "info")
    subprocess.run(["sysctl", "-w", "net.ipv4.conf.all.forwarding=1"], check=True)
    subprocess.run(["sysctl", "-w", "kernel.unprivileged_bpf_disabled=0"], check=True)

    with open("/etc/sysctl.d/99-cilium.conf", "w") as f:
        f.write("net.ipv4.conf.all.forwarding = 1\n")
        f.write("kernel.unprivileged_bpf_disabled = 0\n")

    subprocess.run(["sysctl", "--system"], check=True)
    log("Sysctl параметры применены и сохранены.", "ok")

def ensure_configmap_ca():
    """
    Создаёт configmap с корневым сертификатом, если он отсутствует.
    Ensure kube-root-ca.crt ConfigMap exists in kube-system namespace.
    """

    result = subprocess.run(
        ["kubectl", "get", "configmap", "kube-root-ca.crt", "-n", "kube-system"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        log("Создаю configmap kube-root-ca.crt из /etc/kubernetes/pki/ca.crt", "info")
        subprocess.run([
            "kubectl", "create", "configmap", "kube-root-ca.crt",
            "--from-file=ca.crt=/etc/kubernetes/pki/ca.crt",
            "-n", "kube-system"
        ], check=True)
    else:
        log("ConfigMap kube-root-ca.crt уже существует", "ok")

def wait_for_configmap(name: str, namespace: str, timeout: int = 60):
    """
    Ожидает появления configmap в заданном namespace.
    Wait for a ConfigMap to appear within timeout.
    """
    log(f"Ожидание появления ConfigMap {name} в namespace {namespace} (до {timeout} сек)...", "info")
    for i in range(timeout):
        result = subprocess.run(
            ["kubectl", "get", "configmap", name, "-n", namespace],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            log(f"ConfigMap {name} найден через {i} сек", "ok")
            return
        time.sleep(1)
    log(f"ConfigMap {name} не появился за {timeout} сек", "error")
    sys.exit(1)

def apply_cilium_manifest():
    """
    Удаляет предыдущий манифест Cilium, применяет новый и очищает временные файлы.
    Delete previous Cilium manifest, apply the new one, and clean up temp files.
    """

    if not os.path.exists(CILIUM_YAML_PATH):
        generate_cilium_manifest()

    log("Удаление старой установки Cilium (если есть)...", "info")
    run_shell_cmd(["kubectl", "delete", "-f", CILIUM_YAML_PATH, "--ignore-not-found"])

    log("Применение манифеста Cilium...", "info")
    if run_shell_cmd(["kubectl", "apply", "-f", CILIUM_YAML_PATH]) != 0:
        log("Не удалось применить манифест Cilium", "error")
        sys.exit(1)

#    if os.path.exists(CILIUM_VALUES_RENDERED):
#        os.remove(CILIUM_VALUES_RENDERED)
#        log("Временный файл values для Cilium удалён.", "info")

def mount_bpf_fs():
    """
    Монтирует BPF файловую систему, если она не смонтирована.
    Mount BPF filesystem if not already mounted.
    """
    bpf_path = "/sys/fs/bpf"
    if not os.path.ismount(bpf_path):
        log("Монтирую BPF файловую систему...", "info")
        os.makedirs(bpf_path, exist_ok=True)
        subprocess.run(["mount", "-t", "bpf", "bpffs", bpf_path], check=True)
    else:
        log("BPF уже смонтирован", "ok")

def main():
    """
    Основной процесс установки Cilium и очистки временных настроек.
    Main process to install Cilium and clean up temporary setup.
    """

    log("== Установка Cilium из исходников с удалением временной bridge-сети ==", "start")
    apply_sysctl_settings()
    mount_bpf_fs()
    ensure_configmap_ca()
    ensure_cilium_repo()
    apply_cilium_manifest()
    wait_for_configmap("cilium-config", "kube-system")
    patch_custom_cni_conf()
    cleanup_temporary_bridge()
    log("Cilium установлен, bridge удалён. Можно продолжать установку.", "ok")

if __name__ == "__main__":
    main()
