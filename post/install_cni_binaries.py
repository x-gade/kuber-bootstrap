#!/usr/bin/env python3
"""
Устанавливает Cilium CNI плагин вручную.
Склонирует репозиторий, соберёт бинарники, создаст конфиг из шаблона и перезапустит kubelet.

Installs Cilium CNI plugin manually.
Clones the repo, builds binaries, generates config from template and restarts kubelet.
"""

import os
import sys
import subprocess
from pathlib import Path
from jinja2 import Template

# Добавляем корень проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data import collected_info


# Пути
CILIUM_DIR = "/opt/cni/cilium"
CNI_BIN_DIR = "/opt/cni/bin"
CNI_CONFIG_PATH = "/etc/cni/net.d/10-cilium.conflist"
CNI_TEMPLATE_PATH = "data/cni/cilium.conflist.j2"
CILIUM_BRANCH = "v1.14.6"
GOLANG_PATH = "/usr/local/go/bin/go"


def run(cmd, cwd=None):
    """
    Выполняет команду shell с логированием ошибок.
    Runs a shell command with error logging.
    """

    try:
        subprocess.run(cmd, shell=True, check=True, cwd=cwd)
    except subprocess.CalledProcessError:
        log(f"Ошибка при выполнении команды: {cmd}", "error")
        sys.exit(1)


def check_go():
    """
    Проверяет наличие установленного Go и добавляет его в PATH.
    Checks if Go is installed and adds it to PATH.
    """

    if not Path(GOLANG_PATH).exists():
        log("Go не установлен!", "error")
        sys.exit(1)
    os.environ["PATH"] = f"/usr/local/go/bin:{os.environ['PATH']}"


def clone_or_prepare_repo():
    """
    Клонирует репозиторий Cilium или обновляет существующий.
    Clones or updates the Cilium repository.
    """

    if not Path(CILIUM_DIR).exists():
        log("Клонирование репозитория Cilium...", "info")
        run(f"git clone https://github.com/cilium/cilium.git {CILIUM_DIR}")
    else:
        log("Папка cilium уже существует.", "ok")
        log("Обновление содержимого и проверка ветки...", "info")
        run("git fetch", cwd=CILIUM_DIR)

    run(f"git checkout {CILIUM_BRANCH}", cwd=CILIUM_DIR)
    run("git reset --hard", cwd=CILIUM_DIR)


def build_plugins():
    """
    Собирает CNI плагины с помощью Make.
    Builds CNI plugins using Make.
    """

    log("Сборка CNI плагинов через 'make plugins'...", "info")
    run("make plugins", cwd=CILIUM_DIR)


def copy_binaries():
    """
    Копирует собранный бинарник cilium-cni в директорию CNI.
    Copies the built cilium-cni binary to CNI directory.
    """

    src = Path(f"{CILIUM_DIR}/plugins/cilium-cni/cilium-cni")
    if not src.exists():
        log("Файл cilium-cni не найден после сборки!", "error")
        sys.exit(1)

    Path(CNI_BIN_DIR).mkdir(parents=True, exist_ok=True)
    run(f"cp {src} {CNI_BIN_DIR}/cilium-cni")
    log("Файл cilium-cni успешно установлен в CNI_BIN_DIR.", "ok")


def generate_cni_config():
    """
    Генерирует CNI-конфиг из Jinja2 шаблона, если он ещё не существует.
    Generates CNI config from Jinja2 template if not already exists.
    """

    if Path(CNI_CONFIG_PATH).exists():
        log("CNI конфигурация уже существует: 10-cilium.conflist", "ok")
        return

    if not Path(CNI_TEMPLATE_PATH).exists():
        log(f"Шаблон CNI-конфига не найден: {CNI_TEMPLATE_PATH}", "error")
        sys.exit(1)

    log("Создание CNI-конфигурации из шаблона...", "info")
    with open(CNI_TEMPLATE_PATH) as f:
        template = Template(f.read())

    rendered = template.render(
        public_ip=collected_info.IP,
        service_port="6443",
        pod_cidr=collected_info.CLUSTER_POD_CIDR,
    )

    Path(CNI_CONFIG_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(CNI_CONFIG_PATH, "w") as f:
        f.write(rendered)

    log("Конфигурация CNI успешно сгенерирована из шаблона.", "ok")


def restart_kubelet():
    """
    Перезапускает kubelet и проверяет его статус.
    Restarts kubelet and checks its status.
    """

    log("Перезапуск kubelet для применения CNI...", "info")
    result = subprocess.run(["systemctl", "restart", "kubelet"], capture_output=True, text=True)
    if result.returncode == 0:
        log("kubelet перезапущен.", "ok")
    else:
        log(f"Не удалось перезапустить kubelet:\n{result.stderr}", "error")
        sys.exit(1)

    log("Проверка состояния kubelet...", "info")
    status = subprocess.run(["systemctl", "is-active", "kubelet"], capture_output=True, text=True)
    if status.returncode == 0 and status.stdout.strip() == "active":
        log("kubelet работает нормально.", "ok")
    else:
        log("kubelet НЕ в активном состоянии!", "warn")
        log(f"systemctl is-active: {status.stdout.strip()}", "info")
        subprocess.run("journalctl -u kubelet --no-pager -n 20", shell=True)


def main():
    """
    Основной процесс установки Cilium CNI.
    Main installation routine for Cilium CNI.
    """

    log("Установка бинарников Cilium CNI вручную...", "info")
    check_go()
    clone_or_prepare_repo()
    build_plugins()
    copy_binaries()
    generate_cni_config()
    restart_kubelet()
    log("Установка бинарников завершена.", "ok")


if __name__ == "__main__":
    main()
