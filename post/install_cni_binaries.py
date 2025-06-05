#!/usr/bin/env python3

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import subprocess
from pathlib import Path
from utils.logger import log

CILIUM_DIR = "/opt/cni/cilium"
CNI_BIN_DIR = "/opt/cni/bin"
CNI_CONFIG_PATH = "/etc/cni/net.d/10-cilium.conflist"
CILIUM_BRANCH = "v1.14.6"
GOLANG_PATH = "/usr/local/go/bin/go"

def run(cmd, cwd=None):
    try:
        subprocess.run(cmd, shell=True, check=True, cwd=cwd)
    except subprocess.CalledProcessError:
        log(f"Ошибка при выполнении команды: {cmd}", "error")
        sys.exit(1)

def check_go():
    if not Path(GOLANG_PATH).exists():
        log("Go не установлен!", "error")
        sys.exit(1)
    os.environ["PATH"] = f"/usr/local/go/bin:{os.environ['PATH']}"

def clone_or_prepare_repo():
    if not Path(CILIUM_DIR).exists():
        log("Клонирование репозитория Cilium...", "info")
        run(f"git clone https://github.com/cilium/cilium.git {CILIUM_DIR}")
    else:
        log("Папка cilium уже существует.", "ok")
        log("Обновление содержимого и проверка ветки...", "info")
        run("git fetch", cwd=CILIUM_DIR)

    # Переход на нужную ветку
    run(f"git checkout {CILIUM_BRANCH}", cwd=CILIUM_DIR)
    run("git reset --hard", cwd=CILIUM_DIR)

def build_plugins():
    log("Сборка CNI плагинов через 'make plugins'...", "info")
    run("make plugins", cwd=CILIUM_DIR)

def copy_binaries():
    src_path = Path(f"{CILIUM_DIR}/plugins/cilium-cni/cilium-cni")
    if not src_path.exists():
        log("Файл cilium-cni не найден после сборки!", "error")
        sys.exit(1)

    dst_path = Path(CNI_BIN_DIR)
    dst_path.mkdir(parents=True, exist_ok=True)
    run(f"cp {src_path} {dst_path}/cilium-cni")
    log("Файл cilium-cni успешно установлен в CNI_BIN_DIR.", "ok")

def generate_cni_config():
    if Path(CNI_CONFIG_PATH).exists():
        log("CNI конфигурация уже существует: 10-cilium.conflist", "ok")
        return

    log("Создание CNI-конфигурации 10-cilium.conflist...", "info")
    config = """{
  "cniVersion": "0.3.1",
  "name": "cilium",
  "plugins": [
    {
      "type": "cilium-cni",
      "log-level": "info",
      "mtu": 1450
    }
  ]
}
"""
    os.makedirs(Path(CNI_CONFIG_PATH).parent, exist_ok=True)
    with open(CNI_CONFIG_PATH, "w") as f:
        f.write(config)
    log("Конфигурация CNI создана.", "ok")

def restart_kubelet():
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
        log("Последние логи kubelet (journalctl):", "info")
        subprocess.run("journalctl -u kubelet --no-pager -n 20", shell=True)

def main():
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
