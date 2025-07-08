# setup/install_binaries.py

import os
import sys
import json
import tarfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log

MISSING_FILE = "data/missing_binaries.json"
BINARIES_DIR = Path("binares")
INSTALL_PATH = Path("/usr/local/bin")
TMP_DIR = Path("/tmp")

def install_binary_from_archive(binary: str):
    """
    Extract and install a binary from its archive.
    Распаковывает и устанавливает бинарник из архива.
    """
    archive_path = BINARIES_DIR / f"{binary}.tar.gz"

    if not archive_path.exists():
        log(f"Архив не найден для {binary}: {archive_path}", "error")
        return

    log(f"Установка {binary} из архива...", "info")

    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            if binary == "cilium":
                # Особая логика: извлекаем в binares/cilium/
                target_dir = BINARIES_DIR / "cilium"
                tar.extractall(path=target_dir)
                cli_binary = target_dir / "cilium"
                if cli_binary.exists():
                    cli_binary.chmod(0o755)
                    cli_binary.replace(INSTALL_PATH / "cilium")
                    log(f"cilium CLI установлен в {INSTALL_PATH}/cilium", "ok")
                else:
                    log(f"cilium CLI не найден после распаковки", "error")
                return

            member = next((m for m in tar.getmembers() if m.name == binary), None)
            if not member:
                log(f"{binary} не найден внутри архива {archive_path}", "error")
                return

            tar.extract(member, path=TMP_DIR)
            extracted = TMP_DIR / binary
            extracted.chmod(0o755)

            # Для kubelet — используем /usr/bin
            target_path = Path("/usr/bin") / binary if binary == "kubelet" else INSTALL_PATH / binary

            extracted.replace(target_path)
            log(f"{binary} установлен в {target_path}", "ok")

    except Exception as e:
        log(f"Ошибка при установке {binary}: {e}", "error")

def main():
    """
    Install all missing binaries from tar.gz archives.
    Устанавливает все отсутствующие бинарники из архивов.
    """
    if not os.path.exists(MISSING_FILE):
        log(f"Файл {MISSING_FILE} не найден — установка не требуется", "ok")
        return

    with open(MISSING_FILE, "r") as f:
        data = json.load(f)

    missing = data.get("missing", [])
    if not missing:
        log("Список бинарников пуст — ничего устанавливать", "ok")
        os.remove(MISSING_FILE)
        return

    for binary in missing:
        install_binary_from_archive(binary)

    log("Все бинарники установлены.", "ok")
    os.remove(MISSING_FILE)

if __name__ == "__main__":
    main()
