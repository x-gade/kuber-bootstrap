#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import json

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
sys.path.append(PROJECT_ROOT)

from utils.logger import log

# === Константы ===
CILIUM_REPO = "https://github.com/cilium/cilium.git"
CILIUM_BRANCH = "v1.14.6"
CILIUM_DIR = "/opt/cni/cilium"
CILIUM_HELM_DIR = os.path.join(CILIUM_DIR, "install/kubernetes/cilium")
CILIUM_YAML_PATH = os.path.join(CILIUM_DIR, "install/kubernetes/cilium.yaml")
COLLECTED_INFO_PATH = os.path.join(PROJECT_ROOT, "cluster", "collected_info.json")
CNI_CONFIG_DIR = "/etc/cni/net.d"


def run_shell_cmd(cmd: list, cwd=None, capture=False):
    try:
        result = subprocess.run(cmd, check=True, cwd=cwd, stdout=subprocess.PIPE if capture else None, stderr=subprocess.PIPE if capture else None)
        return result.stdout.decode().strip() if capture else 0
    except subprocess.CalledProcessError as e:
        if capture:
            return e.stderr.decode().strip()
        return 1


def ensure_cilium_repo():
    if os.path.exists(CILIUM_DIR):
        log("Папка cilium уже существует, клонирование не требуется.", "ok")
    else:
        log("Клонируем репозиторий Cilium в /opt/cni/cilium...", "info")
        if run_shell_cmd(["git", "clone", CILIUM_REPO, CILIUM_DIR]) != 0:
            log("Ошибка при клонировании репозитория Cilium.", "error")
            sys.exit(1)

    log(f"Переключение на ветку {CILIUM_BRANCH}...", "info")
    if run_shell_cmd(["git", "checkout", CILIUM_BRANCH], cwd=CILIUM_DIR) != 0:
        log(f"Ошибка при переключении на ветку {CILIUM_BRANCH}", "error")
        sys.exit(1)

    log("Сборка бинарников пропущена — они уже установлены вручную.", "info")


def get_public_ip_and_port():
    try:
        with open(COLLECTED_INFO_PATH, "r") as f:
            data = json.load(f)
            ip = data.get("public_ip")
            port = data.get("apiserver_secure_port", "6443")
            if not ip:
                raise ValueError("Поле public_ip не найдено в collected_info.json")
            return ip, str(port)
    except Exception as e:
        log(f"Ошибка при получении IP и порта из collected_info.json: {e}", "error")
        sys.exit(1)


def generate_cilium_manifest():
    if not shutil.which("helm"):
        log("Helm не найден в системе. Установите его отдельно перед запуском.", "error")
        sys.exit(1)

    ip, port = get_public_ip_and_port()

    log(f"Генерация манифеста Cilium через helm template (host={ip}, port={port})...", "info")

    cmd = [
        "helm", "template", "cilium", CILIUM_HELM_DIR,
        "--namespace", "kube-system",
        "--set", "kubeProxyReplacement=strict",
        "--set", "ipam.mode=kubernetes",
        "--set", "k8s.requireIPv4PodCIDR=true",
        "--set", f"k8sServiceHost={ip}",
        "--set", f"k8sServicePort={port}",
        "--set", "nodeSelector.\"node-role.kubernetes.io/control-plane\"=",
        "--set", "tolerations[0].key=node-role.kubernetes.io/control-plane",
        "--set", "tolerations[0].operator=Exists",
        "--set", "tolerations[0].effect=NoSchedule"
    ]

    try:
        with open(CILIUM_YAML_PATH, "w") as f:
            subprocess.run(cmd, check=True, cwd=PROJECT_ROOT, stdout=f)
    except subprocess.CalledProcessError:
        log("Ошибка при генерации манифеста Helm", "error")
        sys.exit(1)


def cleanup_cni_config():
    log("Очистка каталога CNI: /etc/cni/net.d/...", "info")
    if os.path.exists(CNI_CONFIG_DIR):
        for entry in os.listdir(CNI_CONFIG_DIR):
            entry_path = os.path.join(CNI_CONFIG_DIR, entry)
            if os.path.isfile(entry_path):
                os.remove(entry_path)


def wait_for_rollout(kind, name, namespace, timeout=60):
    log(f"Ожидание rollout для {kind}/{name}...", "info")
    cmd = ["kubectl", "rollout", "status", f"{kind}/{name}", "-n", namespace, "--timeout", f"{timeout}s"]
    result = run_shell_cmd(cmd)
    if result != 0:
        log(f"{kind} {name} не прошел rollout за {timeout} секунд", "error")
        return False
    return True


def check_kubectl_and_apiserver():
    if not shutil.which("kubectl"):
        log("kubectl не найден в системе. Установите его и проверьте $PATH.", "error")
        sys.exit(1)
    try:
        subprocess.run(["kubectl", "get", "nodes"], check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        log("kube-apiserver недоступен. Убедитесь, что он запущен и доступен.", "error")
        sys.exit(1)


def apply_cilium_manifest():
    if not os.path.exists(CILIUM_YAML_PATH):
        generate_cilium_manifest()

    log("Удаление старой установки Cilium (если есть)...", "info")
    run_shell_cmd(["kubectl", "delete", "-f", CILIUM_YAML_PATH, "--ignore-not-found"])
    cleanup_cni_config()

    log("Применение Cilium манифеста напрямую...", "info")
    if run_shell_cmd(["kubectl", "apply", "-f", CILIUM_YAML_PATH]) != 0:
        log("Не удалось применить манифест Cilium", "error")
        sys.exit(1)

    rollout_ok = wait_for_rollout("daemonset", "cilium", "kube-system") and wait_for_rollout("deployment", "cilium-operator", "kube-system")
    if rollout_ok:
        log("Cilium успешно установлен и развернут.", "ok")
    else:
        log("Cilium установлен, но не все компоненты завершили rollout.", "warn")


def restart_apiserver():
    log("Перезапуск kube-apiserver в режиме DEV после установки Cilium...", "info")
    gen_script = os.path.join(PROJECT_ROOT, "systemd", "generate_apiserver_service.py")
    if not os.path.exists(gen_script):
        log("Скрипт generate_apiserver_service.py не найден, пропуск перезапуска apiserver.", "warn")
        return
    result = subprocess.run(["python3", gen_script, "--mode=dev"])
    if result.returncode == 0:
        log("kube-apiserver успешно перезапущен после установки Cilium.", "ok")
    else:
        log("Ошибка при перезапуске kube-apiserver через generate_apiserver_service.py", "error")


if __name__ == "__main__":
    log("Установка Cilium через статичный YAML из исходников...", "start")
    check_kubectl_and_apiserver()
    ensure_cilium_repo()
    apply_cilium_manifest()
    restart_apiserver()
