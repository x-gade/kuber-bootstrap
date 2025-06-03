#!/usr/bin/env python3
import os
import subprocess
import sys

GO_VERSION = "1.20.14"
GO_TARBALL = f"go{GO_VERSION}.linux-amd64.tar.gz"
GO_URL = f"https://go.dev/dl/{GO_TARBALL}"
GO_INSTALL_DIR = "/usr/local"
GO_PROFILE_SCRIPT = "/etc/profile.d/go.sh"


def run(cmd, check=True):
    print(f"[CMD] {' '.join(cmd)}")
    subprocess.run(cmd, check=check)


def main():
    print("[INFO] Удаляем старую версию Go...")
    run(["rm", "-rf", os.path.join(GO_INSTALL_DIR, "go")])

    print(f"[INFO] Загружаем Go {GO_VERSION}...")
    run(["wget", GO_URL])

    print("[INFO] Распаковываем Go в /usr/local ...")
    run(["tar", "-C", GO_INSTALL_DIR, "-xzf", GO_TARBALL])

    print("[INFO] Настраиваем PATH для Go...")
    with open(GO_PROFILE_SCRIPT, "w") as f:
        f.write('export PATH=/usr/local/go/bin:$PATH\n')

    print("[INFO] Применяем PATH (только на текущую сессию)...")
    os.environ["PATH"] = f"/usr/local/go/bin:{os.environ['PATH']}"

    print("[INFO] Проверяем установленную версию Go:")
    run(["go", "version"])

    print("[INFO] Удаляем загруженный архив...")
    if os.path.exists(GO_TARBALL):
        os.remove(GO_TARBALL)
        print(f"[OK] Архив {GO_TARBALL} удалён.")
    else:
        print(f"[WARN] Архив {GO_TARBALL} не найден для удаления.")

    print("[OK] Установка Go завершена.")


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("[ERROR] Этот скрипт нужно запускать от root")
        sys.exit(1)

    try:
        main()
    except subprocess.CalledProcessError:
        print("[ERROR] Во время установки произошла ошибка.")
        sys.exit(1)
