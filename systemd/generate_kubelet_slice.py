#!/usr/bin/env python3

"""
Generates and installs the kubelet.slice unit from Jinja2 template, sets resource limits, and ensures the slice is active.
Генерирует и устанавливает unit-файл kubelet.slice из шаблона Jinja2, задаёт лимиты ресурсов и проверяет, что slice активен.
"""

import os
import sys

# Добавляем путь до корня проекта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import subprocess
from jinja2 import Template
from utils.logger import log

TEMPLATE_PATH = "data/systemd/kubelet.slice.j2"
OUTPUT_PATH = "/etc/systemd/system/kubelet.slice"
COLLECTED_INFO_PATH = "data/collected_info.json"

def ensure_directory_exists(path):
    """
    Ensures the parent directory for the output slice file exists.
    Убеждается, что директория для вывода slice-файла существует.
    """
    dir_path = os.path.dirname(path)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        log(f"Создана директория: {dir_path}", "ok")
    else:
        log(f"Директория уже существует: {dir_path}", "info")

def render_template():
    """
    Renders the Jinja2 template using values from collected_info.json.
    Генерирует содержимое по шаблону Jinja2, используя значения из collected_info.json.
    """
    try:
        with open(TEMPLATE_PATH) as f:
            template = Template(f.read())
        return template.render()
    except Exception as e:
        log(f"Ошибка при рендеринге шаблона: {e}", "error")
        raise

def write_output(content):
    """
    Writes rendered content to the systemd unit file.
    Записывает сгенерированное содержимое в systemd unit-файл.
    """
    try:
        with open(OUTPUT_PATH, "w") as f:
            f.write(content)
        log(f"Unit-файл записан: {OUTPUT_PATH}", "ok")
    except Exception as e:
        log(f"Ошибка при записи unit-файла: {e}", "error")
        raise

def reload_and_restart_slice():
    """
    Reloads systemd and restarts the kubelet.slice unit.
    Перезагружает systemd и запускает kubelet.slice.
    """
    os.system("systemctl daemon-reexec")
    os.system("systemctl daemon-reload")
    result = os.system("systemctl restart kubelet.slice || systemctl start kubelet.slice")
    if result != 0:
        log("Не удалось запустить kubelet.slice", "error")
        return False
    log("Slice kubelet.slice запущен", "ok")
    return True

def verify_slice_active():
    """
    Verifies that the kubelet.slice unit is active.
    Проверяет, что kubelet.slice активен.
    """
    try:
        output = subprocess.check_output(["systemctl", "is-active", "kubelet.slice"]).decode().strip()
        if output == "active":
            log("Проверка: kubelet.slice активен", "ok")
            return True
        else:
            log(f"Slice не активен (статус: {output})", "warn")
            return False
    except subprocess.CalledProcessError as e:
        log(f"Ошибка при проверке состояния slice: {e}", "error")
        return False

def main():
    """
    Main entry point for kubelet.slice generation and activation.
    Основная точка входа для генерации и активации kubelet.slice.
    """
    log("Генерация unit-файла для kubelet.slice...", "info")
    ensure_directory_exists(OUTPUT_PATH)
    content = render_template()
    write_output(content)
    if reload_and_restart_slice():
        verify_slice_active()

if __name__ == "__main__":
    main()
