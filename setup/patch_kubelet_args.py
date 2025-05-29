# setup/patch_kubelet_config.py

import yaml
from pathlib import Path
import subprocess

CONFIG_PATH = Path("/var/lib/kubelet/config.yaml")

def log(msg, level="info"):
    levels = {
        "info": "[INFO]",
        "ok": "[OK]",
        "warn": "[WARN]",
        "error": "[ERROR]"
    }
    print(f"{levels.get(level, '[INFO]')} {msg}")

def patch_config():
    if not CONFIG_PATH.exists():
        log(f"Файл {CONFIG_PATH} не найден", "error")
        return

    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)

    if config.get("allowPrivileged") is True:
        log("allowPrivileged уже включён", "ok")
        return

    config["allowPrivileged"] = True

    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(config, f)

    log("Файл config.yaml обновлён: allowPrivileged включён", "ok")

def reload_kubelet():
    subprocess.run(["systemctl", "restart", "kubelet"], check=True)
    log("kubelet перезапущен", "ok")

def main():
    log("=== Патчинг config.yaml kubelet ===")
    patch_config()
    reload_kubelet()

if __name__ == "__main__":
    main()
