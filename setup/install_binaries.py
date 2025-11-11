#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Install missing CLI binaries from tar archives and (optionally) install CNI plugins.
- Regular binaries: take "<name>.tar.gz" from "binares/" and place to /usr/local/bin
  (or /usr/bin for kubelet).
- Special case "cilium": archive is unpacked to "binares/cilium", then moved to /usr/local/bin.
- Special case "cni-plugins": pick "binares/cni-plugins-linux-amd64-*.tgz" and install
  every file inside to /opt/cni/bin with executable bit.

Устанавливает недостающие CLI-бинарники из tar-архивов и (опционально) CNI-плагины.
- Обычные бинарники: берём "<name>.tar.gz" из "binares/" и кладём в /usr/local/bin
  (или /usr/bin для kubelet).
- Особый случай "cilium": распаковываем в "binares/cilium", затем переносим в /usr/local/bin.
- Особый случай "cni-plugins": находим "binares/cni-plugins-linux-amd64-*.tgz" и
  устанавливаем все файлы внутрь /opt/cni/bin с правами на исполнение.
"""

import os
import sys
import json
import tarfile
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

# доступ к utils.logger
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log  # noqa

MISSING_FILE = "data/missing_binaries.json"
BINARIES_DIR = Path("binares")  # оставляю как в исходнике
INSTALL_PATH = Path("/usr/local/bin")
TMP_DIR = Path("/tmp")

# CNI
CNI_TARGET_DIR = Path("/opt/cni/bin")
CNI_ARCHIVE_GLOB = "cni-plugins-linux-amd64-*.tgz"


def safe_write_atomic(dst: Path, data: bytes, mode: int = 0o755) -> None:
    """
    Atomically write bytes to file (tmp -> fsync -> replace), then chmod.

    Атомарная запись байтов в файл (tmp -> fsync -> replace), затем chmod.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=str(dst.parent), delete=False) as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, dst)
    os.chmod(dst, mode)


def find_cni_archive() -> Optional[Path]:
    """
    Return the latest-matching cni-plugins archive path or None if not found.

    Вернуть путь к «самому свежему» архиву cni-plugins или None, если не найден.
    """
    matches = sorted(BINARIES_DIR.glob(CNI_ARCHIVE_GLOB))
    return matches[-1] if matches else None


def install_cni_plugins(archive_path: Path) -> None:
    """
    Install every regular file from CNI plugins archive into /opt/cni/bin.
    We read each tar member into memory and write atomically, avoiding path traversal.

    Установить все обычные файлы из архива CNI-плагинов в /opt/cni/bin.
    Читаем каждый член tar в память и пишем атомарно — без извлечения путей из архива.
    """
    if not archive_path.exists():
        log(f"CNI archive not found: {archive_path}", "error")
        return

    log(f"Installing CNI plugins from {archive_path} → {CNI_TARGET_DIR}", "info")
    CNI_TARGET_DIR.mkdir(parents=True, exist_ok=True)

    installed = 0
    try:
        with tarfile.open(archive_path, "r:*") as tar:
            for m in tar.getmembers():
                if not m.isfile():
                    continue
                # берём только basename, игнорируя внутренние пути — защита от traversal
                name = os.path.basename(m.name)
                if not name:  # пропускаем странные записи
                    continue
                fobj = tar.extractfile(m)
                if fobj is None:
                    log(f"Skip entry without file object: {m.name}", "warn")
                    continue
                data = fobj.read()
                target = CNI_TARGET_DIR / name
                safe_write_atomic(target, data, mode=0o755)
                installed += 1
                log(f"Installed CNI plugin: {target}", "ok")
    except Exception as e:
        log(f"Error while installing CNI plugins: {e}", "error")
        return

    if installed == 0:
        log("No files were installed from CNI archive (archive empty?)", "warn")
    else:
        log(f"CNI plugins installed: {installed} file(s).", "ok")


def install_binary_from_archive(binary: str) -> None:
    """
    Extract and install a single CLI binary from its "<name>.tar.gz" in 'binares/'.

    Распаковать и установить одиночный CLI-бинарник из "<name>.tar.gz" в 'binares/'.
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
                    log("cilium CLI установлен в /usr/local/bin/cilium", "ok")
                else:
                    log("cilium CLI не найден после распаковки", "error")
                return

            # Обычные бинарники — ищем одноимённый файл внутри архива
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


def main() -> None:
    """
    Install all missing binaries from 'data/missing_binaries.json'.
    Special token "cni-plugins" will trigger installing CNI plugins archive.

    Установить все недостающие бинарники из 'data/missing_binaries.json'.
    Специальный элемент "cni-plugins" триггерит установку архива CNI-плагинов.
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

    # CNI плагинов — отдельная ветка
    if "cni-plugins" in missing:
        archive = find_cni_archive()
        if archive:
            install_cni_plugins(archive)
        else:
            log(f"CNI archive not found by pattern: {BINARIES_DIR}/{CNI_ARCHIVE_GLOB}", "error")

    # Остальные бинарники
    for binary in missing:
        if binary == "cni-plugins":
            continue
        install_binary_from_archive(binary)

    log("Все бинарники установлены.", "ok")
    os.remove(MISSING_FILE)


if __name__ == "__main__":
    main()