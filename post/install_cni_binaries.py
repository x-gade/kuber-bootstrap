#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

CILIUM_DIR = "/opt/cni/cilium"
CNI_BIN_DIR = "/opt/cni/bin"
CNI_CONFIG_PATH = "/etc/cni/net.d/10-cilium.conflist"
CILIUM_BRANCH = "v1.14.6"
GOLANG_PATH = "/usr/local/go/bin/go"

def log(message):
    print(f"[INFO] {message}")

def success(message):
    print(f"[OK] {message}")

def warn(message):
    print(f"[WARN] {message}")

def error(message):
    print(f"[ERROR] {message}")
    sys.exit(1)

def run(cmd, cwd=None):
    try:
        subprocess.run(cmd, shell=True, check=True, cwd=cwd)
    except subprocess.CalledProcessError:
        error(f"Ошибка при выполнении команды: {cmd}")

def check_go():
    if not Path(GOLANG_PATH).exists():
        error("Go не установлен! Установи его перед запуском этого скрипта.")
    os.environ["PATH"] = f"/usr/local/go/bin:{os.environ['PATH']}"

def clone_or_prepare_repo():
    if not Path(CILIUM_DIR).exists():
        log("Клонирование репозитория Cilium...")
        run(f"git clone https://github.com/cilium/cilium.git {CILIUM_DIR}")
    else:
        success("Папка cilium уже существует.")
        log("Обновление содержимого и проверка ветки...")
        run("git fetch", cwd=CILIUM_DIR)

    # Переход на нужную ветку
    run(f"git checkout {CILIUM_BRANCH}", cwd=CILIUM_DIR)
    run("git reset --hard", cwd=CILIUM_DIR)

def build_plugins():
    log("Сборка CNI плагинов через 'make plugins'...")
    run("make plugins", cwd=CILIUM_DIR)

def copy_binaries():
    src_path = Path(f"{CILIUM_DIR}/plugins/cilium-cni/cilium-cni")
    if not src_path.exists():
        error("Файл cilium-cni не найден после сборки!")

    dst_path = Path(CNI_BIN_DIR)
    dst_path.mkdir(parents=True, exist_ok=True)
    run(f"cp {src_path} {dst_path}/cilium-cni")
    success("Файл cilium-cni успешно установлен в CNI_BIN_DIR.")

def generate_cni_config():
    if Path(CNI_CONFIG_PATH).exists():
        success("CNI конфигурация уже существует: 10-cilium.conflist")
        return

    log("Создание CNI-конфигурации 10-cilium.conflist...")
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
    success("Конфигурация CNI создана.")

def restart_kubelet():
    log("Перезапуск kubelet для применения CNI...")
    result = subprocess.run(["systemctl", "restart", "kubelet"], capture_output=True, text=True)
    if result.returncode == 0:
        success("kubelet перезапущен.")
    else:
        error(f"Не удалось перезапустить kubelet:\n{result.stderr}")

    log("Проверка состояния kubelet...")
    status = subprocess.run(["systemctl", "is-active", "kubelet"], capture_output=True, text=True)
    if status.returncode == 0 and status.stdout.strip() == "active":
        success("kubelet работает нормально.")
    else:
        warn("⚠️ kubelet НЕ в активном состоянии!")
        print(f"[DEBUG] systemctl is-active: {status.stdout.strip()}")
        print("[DEBUG] Последние логи kubelet (journalctl):")
        subprocess.run("journalctl -u kubelet --no-pager -n 20", shell=True)

def main():
    print("[START] Установка бинарников Cilium CNI вручную...")
    check_go()
    clone_or_prepare_repo()
    build_plugins()
    copy_binaries()
    generate_cni_config()
    restart_kubelet()
    success("Установка бинарников завершена.")

if __name__ == "__main__":
    main()
