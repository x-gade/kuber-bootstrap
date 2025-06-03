#!/usr/bin/env python3

import os
import subprocess
import textwrap

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
    print(f"[INFO] Проверка директории {CNI_CONFIG_DIR}...")
    os.makedirs(CNI_CONFIG_DIR, exist_ok=True)

    print(f"[INFO] Запись временного CNI-конфига в {CNI_CONFIG_PATH}...")
    with open(CNI_CONFIG_PATH, "w") as f:
        f.write(CNI_CONFIG_CONTENT)
    print("[OK] Конфигурация записана.")

def restore_dns():
    print("[INFO] Проверка и восстановление /etc/resolv.conf...")

    # Если systemd-resolved активен — перезапускаем
    subprocess.run(["systemctl", "restart", "systemd-resolved"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Явно записываем fallback DNS, если systemd-resolved не работает
    try:
        with open("/etc/resolv.conf", "w") as f:
            f.write("nameserver 8.8.8.8\n")
        print("[OK] DNS восстановлен через fallback.")
    except Exception as e:
        print(f"[WARN] Не удалось восстановить DNS: {e}")

def restart_kubelet():
    print("[INFO] Перезапуск kubelet...")
    result = subprocess.run(["systemctl", "restart", "kubelet"], capture_output=True, text=True)
    if result.returncode == 0:
        print("[OK] kubelet успешно перезапущен.")
    else:
        print("[ERROR] Не удалось перезапустить kubelet:")
        print(result.stderr)

def main():
    write_cni_config()
    restore_dns()
    restart_kubelet()
    print("\n[DONE] Временная сеть создана безопасно. Теперь можно устанавливать Cilium.")

if __name__ == "__main__":
    main()
