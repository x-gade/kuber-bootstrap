# setup/install_binaries.py

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import subprocess
from utils.logger import log

ETCD_VERSION = "v3.5.12"
ETCD_URL = f"https://github.com/etcd-io/etcd/releases/download/{ETCD_VERSION}/etcd-{ETCD_VERSION}-linux-amd64.tar.gz"
ARCHIVE_NAME = f"etcd-{ETCD_VERSION}-linux-amd64.tar.gz"
EXTRACTED_FOLDER = f"etcd-{ETCD_VERSION}-linux-amd64"

def run(cmd):
    log(f"[CMD] {' '.join(cmd)}", "info")
    subprocess.run(cmd, check=True)

def main():
    log("Скачивание и установка etcd...", "info")

    os.chdir("/tmp")
    run(["wget", ETCD_URL])
    run(["tar", "xzf", ARCHIVE_NAME])

    # Копируем бинарники
    run(["cp", f"{EXTRACTED_FOLDER}/etcd", "/usr/local/bin/etcd"])
    run(["cp", f"{EXTRACTED_FOLDER}/etcdctl", "/usr/local/bin/etcdctl"])

    # Чистим
    run(["rm", "-rf", ARCHIVE_NAME, EXTRACTED_FOLDER])

    log("etcd установлен в /usr/local/bin", "ok")

if __name__ == "__main__":
    main()
