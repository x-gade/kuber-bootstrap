#!/usr/bin/env python3
"""
Installs essential system dependencies for Kubernetes node initialization.
Добавлен fallback-режим установки clang/llvm/lld и bpftool под Ubuntu 22.04 (Jammy).

Overview / Обзор
----------------
Скрипт устанавливает базовые зависимости узла Kubernetes, затем пытается
поставить toolchain «Jammy» (clang-14/llvm-14/lld-14 и пр.). Если установка
не удалась, используется запасной вариант — безверсионные пакеты (clang/llvm/lld).
Также скрипт подтягивает linux-tools для текущего ядра, находит bpftool и
создаёт на него символическую ссылку в /usr/local/bin, настраивает
update-alternatives и валидирует наличие нужных бинарников в PATH.

Usage / Использование
---------------------
python3 setup/install_dependencies.py
"""

import os
import sys
import shutil
import subprocess
from typing import List

# Подключаем наш логгер
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log  # noqa: E402


BASE_PACKAGES: List[str] = [
    "apt-transport-https",
    "ca-certificates",
    "curl",
    "gnupg",
    "lsb-release",
    "containerd",
    "conntrack",
    "iproute2",
    "sshpass",
    "socat",
]

BPFTOOL_DEPENDENCIES: List[str] = ["libelf1", "zlib1g", "libcap2", "libc6"]

JAMMY_TOOLCHAIN: List[str] = [
    "clang-14",
    "llvm-14",
    "llvm-14-tools",
    "lld-14",
    "make",
    "gcc",
    "libc6-dev",
    "linux-headers-$(uname -r)",
    "linux-tools-$(uname -r)",
    "linux-tools-common",
]

FALLBACK_TOOLCHAIN: List[str] = [
    "clang",
    "llvm",
    "lld",
    "make",
    "gcc",
    "libc6-dev",
    "linux-headers-$(uname -r)",
    "linux-tools-$(uname -r)",
    "linux-tools-common",
]


def run(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    """
    Run a shell command with logging.

    Выполняет команду оболочки с логированием.

    Args:
        cmd: Команда, передаваемая shell.
        check: Если True — возбуждать исключение при ненулевом коде возврата.

    Returns:
        Результат subprocess.run.

    Raises:
        subprocess.CalledProcessError: если check=True и команда завершилась с ошибкой.
    """
    log(f"Выполняю: {cmd}", "info")
    return subprocess.run(cmd, shell=True, check=check, text=True)


def _uname_r() -> str:
    """
    Get current kernel release string (equivalent to `uname -r`).

    Возвращает строку версии текущего ядра (как `uname -r`).

    Returns:
        Строка формата, например: '5.15.0-153-generic'.
    """
    return subprocess.check_output("uname -r", shell=True, text=True).strip()


def install_pkg_list(pkgs: List[str]) -> bool:
    """
    Install a list of packages via apt-get, expanding '$(uname -r)' placeholders.

    Устанавливает список пакетов через apt-get, разворачивая '$(uname -r)'.

    Args:
        pkgs: Список имён пакетов (возможен плейсхолдер $(uname -r)).

    Returns:
        True, если установка прошла успешно; False, если apt вернул ошибку.
    """
    expanded = [p.replace("$(uname -r)", _uname_r()) for p in pkgs]
    try:
        run("apt-get install -y " + " ".join(expanded))
        return True
    except subprocess.CalledProcessError as e:
        log(f"Установка пакетов не удалась: {e}", "warn")
        return False


def ensure_bpftool_symlink() -> None:
    """
    Ensure bpftool is available at /usr/local/bin/bpftool by symlinking from linux-tools.

    Гарантирует наличие bpftool в /usr/local/bin/bpftool, создавая symlink
    на бинарник из установленного пакета linux-tools-*.

    Raises:
        SystemExit: если бинарник bpftool не найден после установки linux-tools.
    """
    result = subprocess.run(
        "find /usr/lib/linux-tools-* -maxdepth 1 -type f -name bpftool | head -n 1",
        shell=True,
        capture_output=True,
        text=True,
    )
    bpftool_path = result.stdout.strip()
    if not bpftool_path:
        log("bpftool не найден после установки linux-tools!", "error")
        sys.exit(1)

    os.makedirs("/usr/local/bin", exist_ok=True)
    target = "/usr/local/bin/bpftool"
    if not os.path.exists(target):
        run(f"ln -s {bpftool_path} {target}")
    log(f"bpftool установлен: {bpftool_path}", "ok")


def set_update_alternatives() -> None:
    """
    Register versioned compilers (clang-14, llc-14, llvm-strip-14, lld-14) as default via update-alternatives.

    Регистрирует версионированные компиляторы как дефолтные через update-alternatives,
    если соответствующие бинарники найдены в системе.
    """
    candidates = {
        "clang": shutil.which("clang-14"),
        "llc": shutil.which("llc-14"),
        "llvm-strip": shutil.which("llvm-strip-14"),
        "lld": shutil.which("lld-14"),
    }
    for name, path in candidates.items():
        if path:
            # check=False: если уже установлен альтернативный вариант, не падать
            run(
                f"update-alternatives --install /usr/bin/{name} {name} {path} 100",
                check=False,
            )


def verify_toolchain() -> None:
    """
    Verify required toolchain binaries exist in PATH.

    Проверяет наличие обязательных бинарников в PATH.

    Required:
        - clang
        - llc
        - llvm-strip
        - bpftool

    Raises:
        SystemExit: если хотя бы один из бинарников отсутствует.
    """
    missing = []
    for b in ["clang", "llc", "llvm-strip", "bpftool"]:
        if shutil.which(b) is None:
            missing.append(b)
    if missing:
        log(f"В PATH отсутствуют: {', '.join(missing)}", "error")
        sys.exit(1)
    log("clang/llc/llvm-strip/bpftool доступны в PATH", "ok")


def install_linux_tools() -> None:
    """
    Install linux-tools for current kernel and ensure bpftool is symlinked.

    Устанавливает linux-tools под текущее ядро и настраивает symlink для bpftool.
    """
    uname = _uname_r()
    log(f"Определено ядро: {uname}", "info")
    # generic — подтянуть общие утилиты; затем конкретный пакет ядра
    run("apt-get install -y linux-tools-generic", check=False)
    run(f"apt-get install -y linux-tools-{uname}", check=False)
    ensure_bpftool_symlink()


def install_toolchain_with_fallback() -> None:
    """
    Install the C toolchain: try Jammy (clang-14/llvm-14) first, then fallback to non-versioned packages.

    Ставит компиляторский toolchain: сперва Jammy-набор (clang-14/llvm-14),
    при неудаче — запасной вариант с безверсионными пакетами.

    Raises:
        SystemExit: если не удалось установить ни основной, ни запасной набор.
    """
    log("Пробуем установить toolchain для Jammy (clang-14/llvm-14)...", "info")
    if install_pkg_list(JAMMY_TOOLCHAIN):
        set_update_alternatives()
        return

    log("Переходим к fallback toolchain (безверсионные пакеты)...", "warn")
    if install_pkg_list(FALLBACK_TOOLCHAIN):
        # Для безверсийных пакетов update-alternatives не требуется.
        return

    log("Не удалось установить ни основной, ни запасной toolchain", "error")
    sys.exit(1)


def install_dependencies() -> None:
    """
    Orchestrate full dependency installation for a Kubernetes node.

    Оркестрирует полную установку зависимостей узла Kubernetes:

      1) apt-get update
      2) базовые пакеты (containerd, conntrack, socat и т.д.)
      3) библиотеки для bpftool
      4) toolchain Jammy -> fallback
      5) linux-tools (для bpftool) + symlink в /usr/local/bin
      6) настройка update-alternatives и финальная проверка
    """
    log("Обновление списка пакетов...", "info")
    run("apt-get update")

    # База
    log(
        f"Установка базовых системных зависимостей: {' '.join(BASE_PACKAGES)}",
        "info",
    )
    run(f"apt-get install -y {' '.join(BASE_PACKAGES)}")

    # Библиотеки для bpftool
    log(
        f"Установка библиотек зависимостей для bpftool: {' '.join(BPFTOOL_DEPENDENCIES)}",
        "info",
    )
    run(f"apt-get install -y {' '.join(BPFTOOL_DEPENDENCIES)}")

    # Toolchain (Jammy -> fallback)
    install_toolchain_with_fallback()

    # Установить/сослать bpftool из linux-tools
    log("Проверяем/устанавливаем bpftool через linux-tools...", "info")
    install_linux_tools()

    # Финальные проверки
    set_update_alternatives()
    verify_toolchain()

    log("Установка всех зависимостей завершена", "ok")


if __name__ == "__main__":
    install_dependencies()
