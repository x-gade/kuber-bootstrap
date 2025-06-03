import os
import subprocess
import sys
from utils.logger import log

INSTALL_MODES = ["control-plane", "node"]

# Очерёдность шагов установки для control-plane
CONTROL_PLANE_STEPS = [
    ("Сбор информации о ноде", "collect_node_info.py"),
    ("Установка зависимостей", "setup/install_dependencies.py"),
    ("Проверка бинарников", "setup/check_binaries.py"),
    ("Установка недостающих бинарников", "setup/install_binaries.py"),
    ("Генерация kubelet конфигурации", "kubelet/generate_kubelet_conf.py"),
    ("Применение ограничений памяти для kubelet", "kubelet/apply_kubelet_memory_override.py"),
    ("Патч kubelet аргументов", "kubelet/patch_kubelet_args.py"),
    ("Включение временной сети bridge", "post/enable_temp_network.py"),
    ("Установка Helm", "setup/install_helm.py"),
    ("Генерация сертификатов", "certs/generate_all.py"),
    ("Генерация kubelet kubeconfig", "kubelet/generate_kubelet_kubeconfig.py"),
    ("Генерация и запуск etcd как systemd unit", "systemd/generate_etcd_service.py"),
    ("Запуск kube-apiserver в режиме DEV", "systemd/generate_apiserver_service.py --mode=dev"),
    ("Генерация kubeadm-конфига", "kubeadm/generate_kubeadm_config.py"),
    ("Генерация admin.kubeconfig", "kubeadm/generate_admin_kubeconfig.py"),
    ("Фазовая инициализация кластера через kubeadm", "kubeadm/run_kubeadm_phases.py"),
    ("Установка Go для сборки Cilium", "post/install_go.py"),
    ("Сборка и установка бинарников Cilium", "post/install_cni_binaries.py"),
    ("Применение CNI манифеста", "post/apply_cni.py"),
    ("Инициализация controller-manager и scheduler", "post/initialize_control_plane_components.py"),
    ("Переключение kube-apiserver в режим PROD", "systemd/generate_apiserver_service.py --mode=prod"),
#    ("Патч controller-менеджера и kube-proxy", "post/patch_controller_flags.py"),
#    ("Генерация команды подключения нод", "post/join_nodes.py"),
]

# Очерёдность шагов установки для worker-ноды
NODE_STEPS = [
    ("Сбор информации о ноде", "collect_node_info.py"),
    ("Установка зависимостей", "setup/install_dependencies.py"),
    ("Проверка бинарников", "setup/check_binaries.py"),
    ("Установка недостающих бинарников", "setup/install_binaries.py"),
    ("Патч kubelet аргументов", "setup/patch_kubelet_args.py"),
    ("Установка Helm", "setup/install_helm.py"),
    ("Получение и выполнение команды join", "post/join_nodes.py"),
]

def run_script(title, command):
    # Пропускаем установку бинарников, если нечего устанавливать
    if "install_binaries.py" in command and not os.path.exists("data/missing_binaries.json"):
        log(f"Пропускаю шаг: {title} — отсутствуют недостающие бинарники", "info")
        return

    log(f"==> {title} [{command}]", "step")
    try:
        parts = command.split()
        script_path = os.path.abspath(parts[0])

        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Файл не найден: {script_path}")

        result = subprocess.run(["python3"] + parts, capture_output=True, text=True)

        if result.returncode != 0:
            log(f"Ошибка в скрипте {command}:", "error")
            print(result.stdout)
            print(result.stderr)
            sys.exit(1)

        print(result.stdout)
        log(f"Завершено: {title}", "ok")

    except Exception as e:
        log(f"Ошибка при выполнении: {title} — {e}", "error")
        sys.exit(1)

def get_mode():
    if len(sys.argv) < 2 or sys.argv[1] not in INSTALL_MODES:
        print(f"Использование: python3 main.py <{'|'.join(INSTALL_MODES)}>")
        sys.exit(1)
    return sys.argv[1]

if __name__ == '__main__':
    mode = get_mode()
    log(f"Запуск установки Kubernetes ({mode})", "info")

    steps = CONTROL_PLANE_STEPS if mode == "control-plane" else NODE_STEPS

    for step_name, script_command in steps:
        run_script(step_name, script_command)

    log("Установка завершена успешно", "ok")
