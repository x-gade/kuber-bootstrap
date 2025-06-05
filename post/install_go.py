#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import subprocess
from utils.logger import log

GO_VERSION = "1.20.14"
GO_TARBALL = f"go{GO_VERSION}.linux-amd64.tar.gz"
GO_URL = f"https://go.dev/dl/{GO_TARBALL}"
GO_INSTALL_DIR = "/usr/local"
GO_PROFILE_SCRIPT = "/etc/profile.d/go.sh"


def run(cmd, check=True):
    log(f"[CMD] {' '.join(cmd)}", "info")
    subprocess.run(cmd, check=check)


def main():
    log("Удаляем старую версию Go...", "info")
    run(["rm", "-rf", os.path.join(GO_INSTALL_DIR, "go")])

    log(f"Загружаем Go {GO_VERSION}...", "info")
    run(["wget", GO_URL])

    log("Распаковываем Go в /usr/local ...", "info")
    run(["tar", "-C", GO_INSTALL_DIR, "-xzf", GO_TARBALL])

    log("Настраиваем PATH для Go...", "info")
    with open(GO_PROFILE_SCRIPT, "w") as f:
        f.write('export PATH=/usr/local/go/bin:$PATH\n')

    log("Применяем PATH (только на текущую сессию)...", "info")
    os.environ["PATH"] = f"/usr/local/go/bin:{os.environ['PATH']}"

    log("Проверяем установленную версию Go:", "info")
    run(["go", "version"])

    log("Удаляем загруженный архив...", "info")
    if os.path.exists(GO_TARBALL):
        os.remove(GO_TARBALL)
        log(f"Архив {GO_TARBALL} удалён.", "ok")
    else:
        log(f"Архив {GO_TARBALL} не найден для удаления.", "warn")

    log("Установка Go завершена.", "ok")


if __name__ == "__main__":
    if os.geteuid() != 0:
        log("Этот скрипт нужно запускать от root", "error")
        sys.exit(1)

    try:
        main()
    except subprocess.CalledProcessError:
        log("Во время установки произошла ошибка.", "error")
        sys.exit(1)
