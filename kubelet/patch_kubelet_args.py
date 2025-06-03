# setup/patch_kubelet_args.py

import os
import sys
import subprocess
from pathlib import Path

# Добавляем корень проекта в sys.path, чтобы импортировать collected_info
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.collected_info import IP as NODE_IP

KUBELET_CONF_PATH = Path("/etc/systemd/system/kubelet.service.d/10-kubeadm.conf")


def log(msg, level="info"):
    levels = {
        "info": "[INFO]",
        "ok": "[OK]",
        "warn": "[WARN]",
        "error": "[ERROR]"
    }
    print(f"{levels.get(level, '[INFO]')} {msg}")


def patch_kubelet_args():
    args_line = f'Environment="KUBELET_EXTRA_ARGS=--allow-privileged=true --node-ip={NODE_IP}"\n'

    if not KUBELET_CONF_PATH.parent.exists():
        log(f"Создаю директорию {KUBELET_CONF_PATH.parent}...", "info")
        KUBELET_CONF_PATH.parent.mkdir(parents=True, exist_ok=True)

    if KUBELET_CONF_PATH.exists():
        with open(KUBELET_CONF_PATH, "r") as f:
            content = f.read()
            if "--node-ip" in content and "--allow-privileged" in content:
                log("Флаги уже указаны в 10-kubeadm.conf", "ok")
                return

    with open(KUBELET_CONF_PATH, "w") as f:
        f.write("[Service]\n")
        f.write(args_line)

    log("Файл 10-kubeadm.conf успешно перезаписан с необходимыми параметрами", "ok")


def reload_systemd():
    subprocess.run(["systemctl", "daemon-reexec"], check=True)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "restart", "kubelet"], check=True)
    log("kubelet перезапущен", "ok")

    # Проверка состояния kubelet
    result = subprocess.run(["systemctl", "is-active", "kubelet"], capture_output=True, text=True)
    status = result.stdout.strip()
    if status == "active":
        log("kubelet работает нормально после перезапуска", "ok")
    else:
        log(f"kubelet не запущен (status: {status}) — проверь логи через 'journalctl -u kubelet'", "error")


def main():
    log("=== Патчинг systemd конфигурации kubelet ===")
    patch_kubelet_args()
    reload_systemd()


if __name__ == "__main__":
    main()
