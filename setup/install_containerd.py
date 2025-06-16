#!/usr/bin/env python3

import os
import sys
import subprocess

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
        result = subprocess.run(
            ["containerd", "config", "default"],
            check=True,
            capture_output=True,
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

if __name__ == "__main__":
    main()
