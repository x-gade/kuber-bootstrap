#!/usr/bin/env python3
"""
    Patcher module for updating CiliumNode with assigned CIDR info.
    Supports --cpb mode, --w (worker mode), or external JSON input.

    Модуль Patcher для обновления объекта CiliumNode.
    Поддерживает режимы --cpb (control-plane bootstrap), --w (worker mode) и внешний JSON-файл.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Добавляем корень проекта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from utils.logger import log

CONTROL_MAP = Path("cluster/ipam_cilium/maps/control_plane_map.json")
WORKER_MAP = Path("cluster/ipam_cilium/maps/worker_map.json")

# kubeconfig для воркера
WORKER_KUBECONFIG = "/etc/kubernetes/admin.conf"

# === Параметры ожиданий ===
DEFAULT_TIMEOUT_SEC = 300          # 5 минут общий таймаут
SLEEP_BETWEEN_TRIES_SEC = 5        # период опроса


def load_entry_from_cpb() -> dict:
    """
    Load node info from control_plane_map.json using current hostname.
    Загружает данные узла из карты control_plane по текущему hostname.
    """
    hostname = os.uname().nodename
    if not CONTROL_MAP.exists():
        raise FileNotFoundError(f"Файл карты не найден: {CONTROL_MAP}")
    data = json.loads(CONTROL_MAP.read_text())
    if hostname not in data:
        raise KeyError(f"Нода {hostname} не найдена в карте {CONTROL_MAP}")
    return data[hostname]


def load_entry_from_worker() -> dict:
    """
    Load node info from worker_map.json directly (worker mode).
    Загружает данные узла из worker_map.json напрямую (режим worker).
    """
    if not WORKER_MAP.exists():
        raise FileNotFoundError(f"Файл worker_map.json не найден: {WORKER_MAP}")
    return json.loads(WORKER_MAP.read_text())


def load_entry_from_file(path: str) -> dict:
    """
    Load node info from external JSON file.
    Загружает данные узла из внешнего JSON-файла.
    """
    f = Path(path)
    if not f.exists():
        raise FileNotFoundError(f"Файл не найден: {f}")
    return json.loads(f.read_text())


def run_kubectl(cmd: list, use_worker_config=False):
    """
    Run kubectl with optional --kubeconfig for worker node.
    Запускает kubectl с опциональным --kubeconfig для воркер-ноды.
    """
    if use_worker_config:
        cmd = ["kubectl", f"--kubeconfig={WORKER_KUBECONFIG}"] + cmd
    else:
        cmd = ["kubectl"] + cmd

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result


def patch_node(name: str, cidr: str, worker_mode=False):
    """
    Patch Kubernetes node with given CIDR.
    Пропатчить Kubernetes-ноду с указанным CIDR.
    """
    patch_payload = f'{{"spec":{{"podCIDR":"{cidr}"}}}}'
    cmd = [
        "patch", "node", name,
        "--type=merge",
        f"-p={patch_payload}"
    ]
    result = run_kubectl(cmd, use_worker_config=worker_mode)

    if result.returncode == 0:
        log(f"Нода {name} успешно пропатчена CIDR {cidr}", "ok")
    else:
        log(f"Ошибка при патче ноды {name}: {result.stderr.decode()}", "error")
        sys.exit(1)


def is_crd_ciliumnode_present(worker_mode=False) -> bool:
    """
    Check if ciliumnodes.cilium.io CRD exists.
    Проверяет наличие CRD ciliumnodes.cilium.io.
    """
    # Быстрый способ: kubectl get crd ciliumnodes.cilium.io
    result = run_kubectl(["get", "crd", "ciliumnodes.cilium.io"], use_worker_config=worker_mode)
    return result.returncode == 0


def wait_for_crd_ciliumnode_established(timeout_sec=DEFAULT_TIMEOUT_SEC, worker_mode=False) -> bool:
    """
    Wait until CiliumNode CRD is present/established (up to timeout).
    Ожидает появления/установления CRD CiliumNode до таймаута.
    """
    start = time.time()
    while True:
        if is_crd_ciliumnode_present(worker_mode=worker_mode):
            # Доп. проверка Established (если поддерживается)
            # Не везде есть condition=Established, но попробуем «мягко»
            result = run_kubectl(
                ["wait", "--for=condition=Established", "--timeout=1s", "crd/ciliumnodes.cilium.io"],
                use_worker_config=worker_mode
            )
            if result.returncode == 0:
                log("CRD ciliumnodes.cilium.io найден и установлен (Established).", "ok")
                return True
            else:
                # Если wait не сработал — всё равно считаем CRD доступным и продолжаем дальше.
                log("CRD ciliumnodes.cilium.io найден, ожидаем доступности API (no Established yet)...", "warn")
                return True

        if time.time() - start >= timeout_sec:
            log("Таймаут ожидания CRD ciliumnodes.cilium.io.", "error")
            return False

        log("Ожидаем появление CRD ciliumnodes.cilium.io...", "info")
        time.sleep(SLEEP_BETWEEN_TRIES_SEC)


def is_ciliumnode_resource_present(name: str, worker_mode=False) -> bool:
    """
    Check if specific CiliumNode resource exists.
    Проверяет, что ресурс CiliumNode/<name> существует.
    """
    result = run_kubectl(["get", "ciliumnode", name], use_worker_config=worker_mode)
    return result.returncode == 0


def wait_for_ciliumnode_resource(name: str, timeout_sec=DEFAULT_TIMEOUT_SEC, worker_mode=False) -> bool:
    """
    Wait until CiliumNode/<name> exists (up to timeout).
    Ожидает появления ресурса CiliumNode/<name> до таймаута.
    """
    start = time.time()
    while True:
        if is_ciliumnode_resource_present(name, worker_mode=worker_mode):
            log(f"CiliumNode {name} обнаружен.", "ok")
            return True

        if time.time() - start >= timeout_sec:
            log(f"Таймаут ожидания ресурса CiliumNode {name}.", "error")
            return False

        log(f"Ожидаем создание CiliumNode {name} агентом (cilium-agent)...", "info")
        time.sleep(SLEEP_BETWEEN_TRIES_SEC)


def patch_cilium_node(name: str, cidr: str, worker_mode=False, timeout_sec=DEFAULT_TIMEOUT_SEC):
    """
    Patch CiliumNode object with podCIDRs via JSON patch.
    Пропатчить объект CiliumNode, добавив podCIDRs через JSON patch.
    Включает ожидания появления CRD и ресурса + ретраи при 404.
    """
    # 1) Дождаться CRD
    if not wait_for_crd_ciliumnode_established(timeout_sec=timeout_sec, worker_mode=worker_mode):
        sys.exit(1)

    # 2) Дождаться конкретного ресурса CiliumNode/<name>
    #    (его создаст cilium-agent после старта)
    if not wait_for_ciliumnode_resource(name, timeout_sec=timeout_sec, worker_mode=worker_mode):
        sys.exit(1)

    # 3) Патч с внутренними ретраями на случай гонок/404
    patch = json.dumps([
        {"op": "add", "path": "/spec/ipam", "value": {}},
        {"op": "add", "path": "/spec/ipam/podCIDRs", "value": [cidr]}
    ])

    deadline = time.time() + timeout_sec
    attempt = 0
    while True:
        attempt += 1
        cmd = ["patch", "ciliumnode", name, "--type=json", "-p", patch]
        result = run_kubectl(cmd, use_worker_config=worker_mode)

        if result.returncode == 0:
            log(f"CiliumNode {name} успешно пропатчен podCIDRs {cidr}", "ok")
            return

        stderr = result.stderr.decode().strip()
        # Если 404/NotFound — подождём и попробуем снова до истечения таймаута
        if "NotFound" in stderr or "the server could not find the requested resource" in stderr:
            if time.time() >= deadline:
                log(f"Ошибка при патче CiliumNode {name} (истёк таймаут ожидания): {stderr}", "error")
                sys.exit(1)
            log(f"[retry {attempt}] CiliumNode {name} ещё не готов (NotFound). Ждём и пробуем снова...", "warn")
            time.sleep(SLEEP_BETWEEN_TRIES_SEC)
            # На всякий случай убедимся, что ресурс есть (если агент только что поднялся)
            wait_for_ciliumnode_resource(name, timeout_sec=SLEEP_BETWEEN_TRIES_SEC * 2, worker_mode=worker_mode)
            continue

        # Любая другая ошибка — фейлим сразу
        log(f"Ошибка при патче CiliumNode {name}: {stderr}", "error")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Patch CiliumNode with CIDR info")
    parser.add_argument("--cpb", action="store_true", help="Режим control-plane bootstrap")
    parser.add_argument("--w", action="store_true", help="Режим worker (читает worker_map.json и использует свой kubeconfig)")
    parser.add_argument("--json", help="Путь до JSON-файла с описанием ноды")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SEC, help="Таймаут ожиданий (сек), по умолчанию 300")

    args = parser.parse_args()

    try:
        worker_mode = False

        if args.cpb:
            node_info = load_entry_from_cpb()
        elif args.w:
            node_info = load_entry_from_worker()
            worker_mode = True  # Включаем использование worker kubeconfig
        elif args.json:
            node_info = load_entry_from_file(args.json)
        else:
            parser.error("Укажите --cpb, --w или --json <path>")

        # Сначала патчим обычную Node — это у тебя уже работало стабильно
        patch_node(node_info["name"], node_info["cidr"], worker_mode=worker_mode)

        # Затем — CiliumNode с «умным» ожиданием CRD и ресурса
        patch_cilium_node(node_info["name"], node_info["cidr"], worker_mode=worker_mode, timeout_sec=args.timeout)

    except Exception as e:
        log(f"[PATCHER] Ошибка: {str(e)}", "error")
        sys.exit(1)
