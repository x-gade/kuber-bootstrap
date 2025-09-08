#!/usr/bin/env python3
<<<<<<< HEAD
=======
# -*- coding: utf-8 -*-

"""
Idempotent installer/maintainer for containerd config.
- Reads the reference config from `data/conf/containerd_conf.toml`.
- Ensures `/etc/containerd/config.toml` exists and matches the reference.
- If it differs, creates a timestamped backup and atomically replaces it.
- Falls back to `containerd config default` when the reference file is missing.

Идемпотентный установщик/поддерживатель конфига containerd.
- Берёт эталонный конфиг из `data/conf/containerd_conf.toml`.
- Гарантирует наличие `/etc/containerd/config.toml` и его соответствие эталону.
- При различиях делает бэкап с меткой времени и атомарно обновляет файл.
- Если эталона нет, использует `containerd config default` как запасной вариант.
"""
>>>>>>> origin/test

import os
import sys
import subprocess
<<<<<<< HEAD

# Добавляем путь до корня проекта, чтобы работал import из utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log

CONFIG_PATH = "/etc/containerd/config.toml"

def check_config_exists() -> bool:
    """
    Check if the containerd config file exists.
    Проверяет, существует ли конфигурационный файл containerd.
    """
    return os.path.isfile(CONFIG_PATH)

def generate_default_config() -> bool:
    """
    Generate the default containerd config file.
    Генерирует конфигурационный файл containerd по умолчанию.
    """
    try:
        log(f"Создаём {CONFIG_PATH} с настройками по умолчанию...", "info")
=======
import shutil
import hashlib
from datetime import datetime
from tempfile import NamedTemporaryFile

# Добавляем путь до корня проекта, чтобы работал import из utils
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from utils.logger import log  # noqa

CONFIG_PATH = "/etc/containerd/config.toml"
SOURCE_CONFIG = os.path.join(PROJECT_ROOT, "data", "conf", "containerd_conf.toml")


def file_sha256(path: str) -> str:
    """
    Compute SHA-256 checksum of a file in a streaming fashion (1 MB chunks).

    Вычислить SHA-256 файла потоково (чанки по 1 МБ).
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def files_differ(src: str, dst: str) -> bool:
    """
    Return True if two files differ by SHA-256 checksum.

    Вернуть True, если файлы различаются по хэшу SHA-256.
    """
    return file_sha256(src) != file_sha256(dst)


def ensure_dir(path: str) -> None:
    """
    Create directory if it does not exist (mkdir -p behavior).

    Создать директорию, если её нет (аналог mkdir -p).
    """
    os.makedirs(path, exist_ok=True)


def write_atomic(dst_path: str, data: bytes, mode: int = 0o644) -> None:
    """
    Atomically write bytes to a file:
    write to a temp file in the same dir -> fsync -> os.replace() -> chmod.

    Атомарная запись байтов в файл:
    запись во временный файл в той же директории -> fsync -> os.replace() -> chmod.
    """
    dir_path = os.path.dirname(dst_path)
    ensure_dir(dir_path)
    with NamedTemporaryFile(dir=dir_path, delete=False) as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = tmp.name
    os.replace(tmp_path, dst_path)
    os.chmod(dst_path, mode)


def backup_file(path: str) -> str:
    """
    Create a timestamped backup next to the target and return its path.

    Создать резервную копию с меткой времени рядом с файлом и вернуть путь к ней.
    """
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    bak = f"{path}.bak.{ts}"
    shutil.copy2(path, bak)
    return bak


def generate_default_config_to(path: str) -> bool:
    """
    Fallback: generate a default containerd config into `path`
    using `containerd config default`. Returns True on success.

    Запасной путь: сгенерировать дефолтный конфиг containerd в `path`
    через `containerd config default`. Возвращает True при успехе.
    """
    try:
        log("Generating default config.toml via `containerd config default`…", "info")
>>>>>>> origin/test
        result = subprocess.run(
            ["containerd", "config", "default"],
            check=True,
            capture_output=True,
<<<<<<< HEAD
            text=True
        )
        with open(CONFIG_PATH, "w") as f:
            f.write(result.stdout)
        log(f"Файл создан: {CONFIG_PATH}", "ok")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Ошибка генерации: {e.stderr}", "error")
        return False
    except Exception as e:
        log(f"Исключение: {e}", "error")
        return False

def main():
    """
    Main script logic.
    Главная логика скрипта.
    """
    log("Проверка конфигурации containerd...", "info")
    if check_config_exists():
        log("Файл уже существует — пропускаем.", "ok")
    else:
        log("Файл не найден. Начинаем генерацию...", "warn")
        success = generate_default_config()
        if success:
            log("Рекомендуется перезапустить containerd: systemctl restart containerd", "warn")
=======
            text=True,
        )
        write_atomic(path, result.stdout.encode("utf-8"))
        log(f"File created: {path}", "ok")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Generation error: {e.stderr}", "error")
        return False
    except Exception as e:
        log(f"Exception during generation: {e}", "error")
        return False


def install_from_source(src: str, dst: str) -> None:
    """
    Install config from `src` to `dst` atomically. Fails if `src` is missing.

    Установить конфиг из `src` в `dst` атомарно. Падает с ошибкой, если нет `src`.
    """
    if not os.path.isfile(src):
        log(f"Reference config not found: {src}", "error")
        raise SystemExit(1)

    with open(src, "rb") as f:
        data = f.read()

    write_atomic(dst, data)
    log(f"Installed config from {src} → {dst}", "ok")


def main() -> None:
    """
    Orchestrate config check & apply:
    - If target is missing → install from reference; fallback to default.
    - If present → compare hashes; backup & replace when different.

    Оркестрация проверки и применения:
    - Если файла нет → ставим из эталона; запасной вариант — дефолтный.
    - Если есть → сравниваем хэши; при различиях делаем бэкап и обновляем.
    """
    log("Checking/updating containerd configuration…", "info")

    # 1) Нет текущего файла — ставим из репозитория (или дефолт)
    if not os.path.isfile(CONFIG_PATH):
        log(f"File not found: {CONFIG_PATH}. Will install from reference.", "warn")
        try:
            install_from_source(SOURCE_CONFIG, CONFIG_PATH)
        except SystemExit:
            # Эталона нет — пробуем дефолтный
            if generate_default_config_to(CONFIG_PATH):
                log("You should restart containerd: systemctl restart containerd", "warn")
            return
        log("You should restart containerd: systemctl restart containerd", "warn")
        return

    # 2) Файл есть — сравним с эталоном
    if not os.path.isfile(SOURCE_CONFIG):
        log(f"Reference config missing: {SOURCE_CONFIG}. Nothing to compare — leaving as is.", "error")
        raise SystemExit(1)

    try:
        if files_differ(SOURCE_CONFIG, CONFIG_PATH):
            old_hash = file_sha256(CONFIG_PATH)
            new_hash = file_sha256(SOURCE_CONFIG)
            bak_path = backup_file(CONFIG_PATH)
            log("Differences found in containerd config.", "warn")
            log(f"Current:  {CONFIG_PATH} sha256={old_hash}", "info")
            log(f"Reference:{SOURCE_CONFIG} sha256={new_hash}", "info")
            log(f"Backup saved: {bak_path}", "ok")

            install_from_source(SOURCE_CONFIG, CONFIG_PATH)
            log("You should restart containerd: systemctl restart containerd", "warn")
        else:
            log("Config is already up to date — no changes required.", "ok")
    except Exception as e:
        log(f"Error while comparing/applying config: {e}", "error")
        raise SystemExit(1)

>>>>>>> origin/test

if __name__ == "__main__":
    main()
