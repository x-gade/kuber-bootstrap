#!/usr/bin/env python3
import os
import sys
import json

# Поднимаемся на один уровень вверх (из cluster → корень проекта)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log  # логгер теперь доступен

"""
Collects join information from user input and saves it to a JSON file.
Собирает информацию для join из ручного ввода пользователя и сохраняет её в JSON-файл.
"""

# Путь к data/join_info.json (на один уровень выше)
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "join_info.json")


def collect_input() -> dict:
    """
    Prompts the user to input all required join parameters.
    Запрашивает у пользователя ввод всех необходимых параметров join.
    """
    log("Введите данные для join:", "info")

    def ask(prompt):
        while True:
            value = input(f"{prompt}: ").strip()
            if value:
                return value
            else:
                log(f"Поле {prompt} не может быть пустым!", "warn")

    return {
        "CONTROL_PLANE_IP": ask("CONTROL_PLANE_IP"),
        "JOIN_TOKEN": ask("JOIN_TOKEN"),
        "DISCOVERY_HASH": ask("DISCOVERY_HASH"),
        "CILIUM_TOKEN": ask("CILIUM_TOKEN"),
        "IPAM_PASSWORD": ask("1IPAM_PASSWORD"),
    }


def save_to_json(data: dict):
    """
    Saves collected data into a JSON file.
    Сохраняет собранные данные в JSON-файл.
    """
    # Создаём data, если нет
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        log(f"Данные успешно сохранены в {OUTPUT_FILE}", "ok")
    except Exception as e:
        log(f"Ошибка при сохранении файла: {e}", "error")


def main():
    """
    Main function to collect and save join info.
    Основная функция для сбора и сохранения данных join.
    """
    log("Сбор данных для join", "info")
    join_info = collect_input()
    save_to_json(join_info)
    log("Готово!", "ok")


if __name__ == "__main__":
    main()
