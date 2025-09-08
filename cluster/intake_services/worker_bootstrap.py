#!/usr/bin/env python3
"""
Worker Bootstrap Script
Подключается к control-plane по SSH, регистрирует воркер-ноду через register
и сохраняет полученный JSON в cluster/ipam_cilium/maps/worker_map.json
"""

"""
Module purpose and flow (EN)
    This script bootstraps a Kubernetes worker node by:
      1) Ensuring local SSH prerequisites (known_hosts file);
      2) Loading local node facts from data/collected_info.py;
      3) Loading join parameters from data/join_info.json;
      4) Performing SSH connection to the control-plane (by password or key);
      5) Executing remote "register" command and parsing JSON from stdout;
      6) Saving the received IPAM allocation JSON into worker_map.json.

    The script exits with non-zero status on critical failures and logs
    all major steps via utils.logger.log.

Назначение модуля и порядок работы (RU)
    Скрипт подготавливает и регистрирует воркер-ноду Kubernetes:
      1) Гарантирует наличие SSH-предпосылок (known_hosts);
      2) Загружает факты о ноде из data/collected_info.py;
      3) Читает параметры подключения из data/join_info.json;
      4) Подключается к control-plane по паролю или по ключу;
      5) Выполняет удалённую команду "register" и парсит JSON из stdout;
      6) Сохраняет полученный JSON-ответ IPAM в worker_map.json.

    При критических ошибках завершает работу с ненулевым кодом,
    ключевые этапы логируются через utils.logger.log.
"""

import sys, json, subprocess, re, os
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CLUSTER_MAPS_DIR = PROJECT_ROOT / "cluster" / "ipam_cilium" / "maps"
WORKER_MAP_FILE = CLUSTER_MAPS_DIR / "worker_map.json"
SSH_KEY_PATH = Path.home() / ".ssh" / "ipam-client.key"

sys.path.insert(0, str(PROJECT_ROOT))
from utils.logger import log

SSH_PORT = "3333"
REMOTE_USER = "ipam-client"


def ensure_known_hosts():
    """
    Ensure local SSH known_hosts file exists with secure permissions (EN)
        Creates ~/.ssh (0700) if missing and ensures ~/.ssh/known_hosts (0600)
        exists. Does not alter existing content. This prevents interactive SSH
        prompts during non-interactive automation runs.

    Гарантирует наличие known_hosts с безопасными правами (RU)
        Создаёт ~/.ssh (0700), если отсутствует, и файл ~/.ssh/known_hosts (0600),
        если его нет. Содержимое не изменяет. Это исключает интерактивные
        вопросы SSH в автоматизированных сценариях.
    """
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    kh = ssh_dir / "known_hosts"
    if not kh.exists():
        kh.touch(mode=0o600)


def load_collected_info():
    """
    Load local node facts from data/collected_info.py (EN)
        Executes the Python file and extracts HOSTNAME, IP, ROLE. Exits on
        absence. Returns a dict: {"hostname": str, "ip": str, "role": str}.

    Загрузка локальных фактов ноды из data/collected_info.py (RU)
        Исполняет Python-файл и извлекает HOSTNAME, IP, ROLE. Завершает работу
        при отсутствии. Возвращает словарь: {"hostname": str, "ip": str, "role": str}.
    """
    collected_file = DATA_DIR / "collected_info.py"
    if not collected_file.exists():
        log("Файл collected_info.py не найден! Запустите collect_node_info.py", "error"); sys.exit(1)
    ns = {}
    exec(collected_file.read_text(), ns)
    for r in ["HOSTNAME","IP","ROLE"]:
        if r not in ns:
            log(f"Не найден параметр {r} в collected_info.py", "error"); sys.exit(1)
    return {"hostname": ns["HOSTNAME"], "ip": ns["IP"], "role": ns["ROLE"]}


def load_join_info():
    """
    Load join parameters from data/join_info.json (EN)
        Requires CONTROL_PLANE_IP and JOIN_TOKEN keys. Optionally reads
        IPAM_PASSWORD (defaults to empty string). Returns the parsed dict.

    Загрузка параметров присоединения из data/join_info.json (RU)
        Требует наличия ключей CONTROL_PLANE_IP и JOIN_TOKEN. Опционально читает
        IPAM_PASSWORD (по умолчанию пустая строка). Возвращает прочитанный словарь.
    """
    join_file = DATA_DIR / "join_info.json"
    if not join_file.exists():
        log("Файл join_info.json не найден! Скопируйте его с control-plane", "error"); sys.exit(1)
    with open(join_file, "r", encoding="utf-8") as f:
        jd = json.load(f)
    for r in ["CONTROL_PLANE_IP","JOIN_TOKEN"]:
        if r not in jd:
            log(f"Не найден параметр {r} в join_info.json", "error"); sys.exit(1)
    # пароль опционален
    jd.setdefault("IPAM_PASSWORD", "")
    return jd


def is_valid_private_key(path: Path) -> bool:
    """
    Check whether the given file looks like a valid OpenSSH/RSA/ED25519 private key (EN)
        Performs a cheap validation: file exists, not too small, and starts with a known
        PEM header. Returns True/False. Exceptions are swallowed, returning False.

    Проверяет, похож ли файл на валидный приватный ключ OpenSSH/RSA/ED25519 (RU)
        Выполняет быструю проверку: файл существует, не слишком маленький и содержит
        известный PEM-заголовок. Возвращает True/False. Исключения подавляются,
        возвращается False.
    """
    try:
        if not path.exists() or path.stat().st_size < 64:
            return False
        head = path.read_text(errors="ignore").strip()
        return "BEGIN OPENSSH PRIVATE KEY" in head or "BEGIN RSA PRIVATE KEY" in head or "BEGIN ED25519 PRIVATE KEY" in head
    except Exception:
        return False


def build_ssh_cmd(control_plane_ip: str, password: str | None, remote_cmd: str) -> list[str]:
    """
    Construct SSH command for password or key-based authentication (EN)
        Uses port SSH_PORT and disables strict host key handling for automation.
        - If 'password' is provided: uses 'sshpass' to invoke ssh without '-i'.
        - Otherwise: requires a valid private key at SSH_KEY_PATH, uses 'ssh -i'.
        Returns the argv list for subprocess.run.

        Parameters:
            control_plane_ip: str  - control-plane public IP
            password        : str|None - password for sshpass, or None to use key
            remote_cmd      : str  - command to execute remotely

        Returns:
            list[str]: fully-built argv for subprocess

        Side effects / Exit:
            Logs errors and exits if key mode selected but key is invalid.

    Конструирует SSH-команду для пароля или ключа (RU)
        Использует порт SSH_PORT и отключает строгую проверку хост-ключей для автоматизации.
        - Если передан 'password': применяет 'sshpass', ssh без '-i'.
        - Иначе: требует валидный ключ в SSH_KEY_PATH и использует 'ssh -i'.
        Возвращает список аргументов для subprocess.run.

        Параметры:
            control_plane_ip: str        - публичный IP control-plane
            password        : str|None   - пароль для sshpass или None для ключа
            remote_cmd      : str        - удалённая команда

        Возвращает:
            list[str]: полностью сформированный argv для subprocess

        Побочные эффекты / Завершение:
            Логирует ошибки и завершает работу, если выбран режим ключа, но ключ не валиден.
    """
    base = [
        "-p", SSH_PORT,
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
    ]
    if password:
        # парольный режим — НЕ добавляем -i
        return ["sshpass", "-p", password, "ssh", *base, f"{REMOTE_USER}@{control_plane_ip}", remote_cmd]
    else:
        # режим ключа — добавим -i только если ключ валиден
        if is_valid_private_key(SSH_KEY_PATH):
            return ["ssh", "-i", str(SSH_KEY_PATH), *base, f"{REMOTE_USER}@{control_plane_ip}", remote_cmd]
        else:
            log(f"Ключ {SSH_KEY_PATH} отсутствует или поврежден. Для ключевого режима положите валидный ключ "
                f"или укажите IPAM_PASSWORD в data/join_info.json", "error")
            sys.exit(1)


def ssh_register_node(control_plane_ip, node_info, token, password: str | None):
    """
    Register the worker node on the control-plane via SSH and parse JSON response (EN)
        Builds a remote "register" command from provided node_info and token,
        runs it over SSH, logs stderr as warnings (host key additions, libcrypto
        messages, etc.). Extracts the first JSON object from stdout (greedy)
        and returns it as a Python dict. Exits on SSH failure or invalid JSON.

        Parameters:
            control_plane_ip: str                 - control-plane IP
            node_info       : dict               - {"hostname": str, "ip": str, "role": str}
            token           : str                - join token
            password        : str|None           - optional password for sshpass

        Returns:
            dict: parsed JSON with at least 'cidr' field typically present

    Регистрирует воркер-ноду на control-plane по SSH и разбирает JSON-ответ (RU)
        Формирует удалённую команду "register" из node_info и token, выполняет её
        по SSH, stderr логируется как предупреждение (host key add, libcrypto и т.п.).
        Извлекает первый JSON-объект из stdout (жадным поиском) и возвращает его
        как словарь. Завершает работу при ошибке SSH или некорректном JSON.

        Параметры:
            control_plane_ip: str                 - IP control-plane
            node_info       : dict               - {"hostname": str, "ip": str, "role": str}
            token           : str                - токен присоединения
            password        : str|None           - пароль для sshpass (опционально)

        Возвращает:
            dict: разобранный JSON, обычно содержит поле 'cidr'
    """
    hostname, node_ip, role = node_info["hostname"], node_info["ip"], node_info["role"]
    remote_cmd = f"register --host 127.0.0.1 --hostname {hostname} --ip {node_ip} --role {role} --token {token}"
    cmd = build_ssh_cmd(control_plane_ip, password, remote_cmd)

    log(f"Подключение к control-plane {control_plane_ip}:{SSH_PORT} и регистрация ноды...", "info")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if result.stderr.strip():
            # libcrypto warning, hostkey add и т.п. — как warn
            log(f"STDERR: {result.stderr.strip()}", "warn")
        m = re.search(r"\{.*\}", result.stdout, re.DOTALL)
        if not m:
            log("Ответ сервера не содержит корректного JSON", "error")
            print(result.stdout); sys.exit(1)
        data = json.loads(m.group(0))
        log(f"Регистрация успешна. CIDR: {data.get('cidr','?')}", "ok")
        return data
    except subprocess.CalledProcessError as e:
        log(f"Ошибка SSH подключения: {e}", "error")
        print("STDOUT:", e.stdout); print("STDERR:", e.stderr); sys.exit(1)


def save_worker_map(data):
    """
    Persist the received IPAM response into worker_map.json (EN)
        Ensures the maps directory exists and writes the JSON with indentation.
        Overwrites any existing file.

        Parameters:
            data: dict - JSON-serializable mapping returned by the register call

    Сохраняет полученный IPAM-ответ в worker_map.json (RU)
        Гарантирует существование директории карт и сохраняет JSON с отступами.
        Перезаписывает существующий файл.

        Параметры:
            data: dict - JSON-структура, полученная от регистрации
    """
    CLUSTER_MAPS_DIR.mkdir(parents=True, exist_ok=True)
    with open(WORKER_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    log(f"Ответ сервера сохранён в {WORKER_MAP_FILE}", "ok")


def main():
    """
    Entry point: orchestrate worker bootstrap flow (EN)
        1) Prepare known_hosts; 2) Load node facts; 3) Verify role=worker;
        4) Load join info; 5) Remove old host key for [IP]:PORT; 6) Register via SSH;
        7) Save IPAM map JSON; exit with proper code on failures.

    Точка входа: оркестрация bootstrap воркер-ноды (RU)
        1) Подготовка known_hosts; 2) Загрузка фактов ноды; 3) Проверка role=worker;
        4) Загрузка join info; 5) Удаление старого хост-ключа для [IP]:PORT; 6) Регистрация по SSH;
        7) Сохранение JSON карты IPAM; корректное завершение при ошибках.
    """
    log("Bootstrap воркер-ноды...", "info")
    ensure_known_hosts()
    node_info = load_collected_info()
    if node_info["role"] != "worker":
        log(f"Роль ноды не worker (ROLE={node_info['role']}). Прерывание.", "error"); sys.exit(1)
    join_info = load_join_info()

    # опционально удалим старую запись known_hosts для IP:PORT
    subprocess.run(["ssh-keygen", "-R", f"[{join_info['CONTROL_PLANE_IP']}]:{SSH_PORT}"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    pw = (join_info.get("IPAM_PASSWORD") or "").strip() or None
    data = ssh_register_node(join_info["CONTROL_PLANE_IP"], node_info, join_info["JOIN_TOKEN"], pw)
    save_worker_map(data)


if __name__ == "__main__":
    main()
