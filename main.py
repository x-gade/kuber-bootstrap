import os
import importlib.util
import sys
from utils.logger import log

# Очерёдность выполнения шагов
STEPS = [
    ("Сбор информации о ноде", "collect_node_info.py"),

    # Установка зависимостей и бинарников
    ("Установка зависимостей", "setup/install_dependencies.py"),
    ("Проверка бинарников", "setup/check_binaries.py"),
    ("Установка недостающих бинарников", "setup/install_binaries.py"),
    ("Патч kubelet аргументов", "setup/patch_kubelet_args.py"),
    ("Установка Helm", "setup/install_helm.py"),

    # Генерация сертификатов и systemd юнитов
    ("Генерация сертификатов", "certs/generate_all.py"),
    ("Генерация и запуск etcd как systemd unit", "systemd/generate_etcd_service.py"),
    ("Генерация и запуск kube-apiserver", "systemd/generate_apiserver_service.py"),

    # Kubeadm конфигурации и инициализация
    ("Генерация kubeadm-конфига", "kubeadm/generate_kubeadm_config.py"),
    ("Генерация admin.kubeconfig", "kubeadm/generate_admin_kubeconfig.py"),

    # Установка сетевого плагина
    ("Установка Go для сборки Cilium", "post/install_go.py"),
    ("Сборка и установка бинарников Cilium", "post/install_cni_binaries.py"),
    ("Применение CNI манифеста", "post/apply_cni.py"),

    # Финальные действия (опционально)
    ("Патч controller-менеджера и kube-proxy", "post/patch_controller_flags.py"),
    ("Генерация команды подключения нод", "post/join_nodes.py"),
]


def run_script(title, path):
    log.step(f"==> {title} [{path}]")
    try:
        path = os.path.abspath(path)
        spec = importlib.util.spec_from_file_location("module.name", path)
        foo = importlib.util.module_from_spec(spec)
        sys.modules["module.name"] = foo
        spec.loader.exec_module(foo)
        log.success(f"Завершено: {title}")
    except Exception as e:
        log.error(f"Ошибка при выполнении: {title} — {e}")
        sys.exit(1)


if __name__ == '__main__':
    log.header("Запуск установки Kubernetes Control Plane")
    for step_name, script_path in STEPS:
        run_script(step_name, script_path)
    log.success("Установка завершена успешно!")
