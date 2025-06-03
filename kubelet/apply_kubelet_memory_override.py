#!/usr/bin/env python3

import os
import shutil
from pathlib import Path
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log

TEMPLATE_SRC = "data/kubelet_override.conf"
TARGET_DIR = "/etc/systemd/system/kubelet.service.d"
TARGET_PATH = os.path.join(TARGET_DIR, "99-override-memory.conf")

def apply_override():
    if not os.path.exists(TEMPLATE_SRC):
        log(f"Файл шаблона не найден: {TEMPLATE_SRC}", "error")
        sys.exit(1)

    os.makedirs(TARGET_DIR, exist_ok=True)
    shutil.copyfile(TEMPLATE_SRC, TARGET_PATH)
    log(f"Override-файл скопирован в: {TARGET_PATH}", "ok")

def reload_systemd():
    os.system("systemctl daemon-reexec")
    os.system("systemctl daemon-reload")
    log("Systemd перезагружен", "ok")

def main():
    apply_override()
    reload_systemd()
    log("Перезапуск kubelet НЕ выполняется — он будет произведён на следующем этапе", "info")

if __name__ == "__main__":
    main()
