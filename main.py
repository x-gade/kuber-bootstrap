#!/usr/bin/env python3
import os
import subprocess
import sys
import argparse
import argcomplete
from utils.logger import log

INSTALL_MODES = ["control-plane", "worker"]

# Очерёдность шагов установки для control-plane
CONTROL_PLANE_STEPS = [
    ("Сбор информации о ноде", "data/collect_node_info.py control-plane"),
    ("Установка зависимостей", "setup/install_dependencies.py"),
    ("Проверка бинарников", "setup/check_binaries.py control-plane"),
    ("Установка недостающих бинарников", "setup/install_binaries.py"),
    ("Установка конифгурационного файла containered", "setup/install_containerd.py"),
    ("Генерация kubelet конфигурации", "kubelet/generate_kubelet_conf.py -cp"),
    ("Применение ограничений памяти для kubelet", "kubelet/manage_kubelet_config.py --mode memory"),
    ("Патч kubelet аргументов", "kubelet/manage_kubelet_config.py --mode bootstrap"),
#    ("Включение временной сети bridge", "post/enable_temp_network.py"),
    ("Установка Helm", "setup/install_helm.py"),
    ("Генерация сертификатов", "certs/generate_all.py"),
    ("Генерация kubelet kubeconfig", "kubelet/generate_kubelet_kubeconfig.py"),
    ("Генерация и запуск etcd как systemd unit", "systemd/generate_etcd_service.py"),
    ("Запуск kube-apiserver в режиме DEV", "systemd/generate_apiserver_service.py --mode=dev"),

    ("Генерация kubeadm-конфига", "kubeadm/generate_kubeadm_config.py"),
    ("Генерация admin.kubeconfig", "kubeadm/generate_admin_kubeconfig.py"),
    ("Фазовая инициализация кластера через kubeadm", "kubeadm/run_kubeadm_phases.py"),
    ("Генерация и запуск controller-manager как systemd unit", "systemd/generate_controller_manager_service.py"),
    ("Генерация и запуск scheduler как systemd unit", "systemd/generate_scheduler_service.py"),

    ("Назначение роли control-plane ноде", "post/label_node.py"),

    ("Добавление бинарника и конфига cilium-cni для kubelet", "post/install_cilium_cni.py"),
    ("Применение RBAC для корректной связи с kubelet", " kubelet/apply_rbacs.py"),
    ("Применение CRD для cilium-agent", "post/apply_crds_cilium.py"),
    ("Создание cilium-agent systemd сервиса", "systemd/generate_cilium_service.py"),
#    ("Проверка и подготовка маунтов BPF и cgroup2 для работы Cilium", "post/verify_bpf_mount.py"),
#    ("Установка Cilium","post/generate_cilium_values.py"),
    ("Запуск kube-apiserver в режиме DEV", "systemd/generate_apiserver_service.py --mode=dev"),
    ("Патч kubelet для продовой среды", "kubelet/manage_kubelet_config.py --mode flags"),
#    ("Установка CoreDNS и проверка компонентов", "post/initialize_coredns.py"),
#    ("Переключение kube-apiserver в режим PROD", "systemd/generate_apiserver_service.py --mode=prod"),

#    ("Назначение роли control-plane ноде", "post/label_node.py"),
    ("Сбор информации о ноде", "data/collect_node_info.py -cpb"),

]

# Очерёдность шагов установки для worker-ноды
WORKER_STEPS = [
    ("Сбор информации о ноде", "data/collect_node_info.py worker"),
    ("Установка зависимостей", "setup/install_dependencies.py"),
    ("Проверка бинарников", "setup/check_binaries.py worker"),
    ("Установка недостающих бинарников", "setup/install_binaries.py"),
    ("Патч сети для возможности подключить ноду", "post/network_patch.py"),
    ("Генерация kubelet config", "kubelet/generate_kubelet_conf.py -w"),
    ("Установка systemd сервиса Kubelet.services из бинарника", "systemd/generate_kubelet_service.py"),
    ("Установка systemd сервиса kubelet.slise", "systemd/generate_kubelet_slice.py"),
    ("Патч kubelet аргументов", "kubelet/manage_kubelet_config.py --mode bootstrap"),
    ("Патч kubelet аргументов", "kubelet/manage_kubelet_config.py --mode flags"),
    ("Получение и выполнение команды join", "post/join_nodes.py"),
]

def run_script(title, command):
    if "install_binaries.py" in command and not os.path.exists("data/missing_binaries.json"):
        log(f"Пропускаю шаг: {title} — отсутствуют недостающие бинарники", "info")
        return

    log(f"==> {title} [{command}]", "step")
    try:
        parts = command.split()
        script_path = os.path.abspath(parts[0])

        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Файл не найден: {script_path}")

        result = subprocess.run(["python3"] + parts, stdout=sys.stdout, stderr=sys.stderr)

        if result.returncode != 0:
            log(f"Ошибка в скрипте {command}", "error")
            sys.exit(1)

        log(f"Завершено: {title}", "ok")

    except Exception as e:
        log(f"Ошибка при выполнении: {title} — {e}", "error")
        sys.exit(1)

def get_mode():
    """
    Парсит аргумент установки (control-plane или worker) с поддержкой автодополнения.
    """
    parser = argparse.ArgumentParser(description="Запуск установки Kubernetes")
    parser.add_argument(
        "mode",
        choices=INSTALL_MODES,
        help="Режим установки: control-plane или worker"
    )

    # Автоматически активируем autocompletion только если переменная окружения выставлена
    if "_ARGCOMPLETE" in os.environ:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()
    return args.mode

if __name__ == '__main__':
    mode = get_mode()
    log(f"Запуск установки Kubernetes ({mode})", "info")

    steps = CONTROL_PLANE_STEPS if mode == "control-plane" else WORKER_STEPS

    for step_name, script_command in steps:
        run_script(step_name, script_command)

    log("Установка завершена успешно", "ok")
