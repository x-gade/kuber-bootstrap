#!/usr/bin/env python3

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import subprocess
import textwrap
from utils.logger import log

CNI_CONFIG_PATH = "/etc/cni/net.d/10-bridge-temporary.conf"
CNI_CONFIG_DIR = os.path.dirname(CNI_CONFIG_PATH)

CNI_CONFIG_CONTENT = textwrap.dedent("""
{
  "cniVersion": "0.3.1",
  "name": "temporary-bridge",
  "type": "bridge",
  "bridge": "cni0",
  "isGateway": false,
  "ipMasq": true,
  "ipam": {
    "type": "host-local",
    "subnet": "10.12.0.0/16",
    "routes": []
  }
}
""").strip()

def write_cni_config():
    log(f"Проверка директории {CNI_CONFIG_DIR}...", "info")
    os.makedirs(CNI_CONFIG_DIR, exist_ok=True)

    log(f"Запись временного CNI-конфига в {CNI_CONFIG_PATH}...", "info")
    with open(CNI_CONFIG_PATH, "w") as f:
        f.write(CNI_CONFIG_CONTENT)
    log("Конфигурация записана.", "ok")

def restore_dns():
    log("Проверка и восстановление /etc/resolv.conf...", "info")

    subprocess.run(["systemctl", "restart", "systemd-resolved"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        with open("/etc/resolv.conf", "w") as f:
            f.write("nameserver 8.8.8.8\n")
        log("DNS восстановлен через fallback.", "ok")
    except Exception as e:
        log(f"Не удалось восстановить DNS: {e}", "warn")

def restart_kubelet():
    log("Перезапуск kubelet...", "info")
    result = subprocess.run(["systemctl", "restart", "kubelet"], capture_output=True, text=True)
    if result.returncode == 0:
        log("kubelet успешно перезапущен.", "ok")
    else:
        log("Не удалось перезапустить kubelet:", "error")
        log(result.stderr, "error")

    # Проверка состояния после перезапуска
    log("Проверка статуса kubelet после перезапуска...", "info")
    status = subprocess.run(["systemctl", "is-active", "kubelet"], capture_output=True, text=True)
    if status.returncode == 0 and status.stdout.strip() == "active":
        log("kubelet работает нормально.", "ok")
    else:
        log("kubelet НЕ запущен после перезапуска!", "error")
        log(f"stdout: {status.stdout.strip()}", "info")
        log(f"stderr: {status.stderr.strip()}", "info")

def main():
    write_cni_config()
    restore_dns()
    restart_kubelet()
    log("\nВременная сеть создана безопасно. Теперь можно устанавливать Cilium.", "ok")

if __name__ == "__main__":
    main()
