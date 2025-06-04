# setup/install_binaries.py

import os
import subprocess
import sys

ETCD_VERSION = "v3.5.12"
ETCD_URL = f"https://github.com/etcd-io/etcd/releases/download/{ETCD_VERSION}/etcd-{ETCD_VERSION}-linux-amd64.tar.gz"
ARCHIVE_NAME = f"etcd-{ETCD_VERSION}-linux-amd64.tar.gz"
EXTRACTED_FOLDER = f"etcd-{ETCD_VERSION}-linux-amd64"

def run(cmd):
    print(f"[CMD] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def main():
    print("[INFO] Скачивание и установка etcd...")

    os.chdir("/tmp")
    run(["wget", ETCD_URL])
    run(["tar", "xzf", ARCHIVE_NAME])

    # Копируем бинарники
    run(["cp", f"{EXTRACTED_FOLDER}/etcd", "/usr/local/bin/etcd"])
    run(["cp", f"{EXTRACTED_FOLDER}/etcdctl", "/usr/local/bin/etcdctl"])

    # Чистим
    run(["rm", "-rf", ARCHIVE_NAME, EXTRACTED_FOLDER])

    print("[OK] etcd установлен в /usr/local/bin")

if __name__ == "__main__":
    main()
