#!/usr/bin/env python3
"""
Worker node deletion & local cleanup orchestrator (EN)
    This script removes a Kubernetes worker node from the control-plane
    via SSH (invoking a remote CLI 'delete') and then performs a local
    reset/cleanup sequence on the node:
      1) Stop & disable kubelet;
      2) kubeadm reset -f;
      3) Remove kube/cni/cilium-related state (including BPF paths);
      4) Restart the container runtime (containerd by default);
      5) Optionally unmount bpffs if mounted and no longer needed.
    SSH supports both password and key-based auth. Errors on the remote
    deletion step do not prevent local cleanup from running. Logging is
    performed through utils.logger.log.

Оркестрация удаления воркер-ноды и локальной очистки (RU)
    Скрипт удаляет воркер-ноду с control-plane по SSH (удалённый CLI 'delete'),
    после чего выполняет локальный сброс/очистку на ноде:
      1) Остановка и отключение kubelet;
      2) kubeadm reset -f;
      3) Удаление состояния kube/cni/cilium (включая пути BPF);
      4) Перезапуск контейнерного рантайма (по умолчанию containerd);
      5) Опциональное размонтирование bpffs, если смонтирован и более не нужен.
    Поддерживаются парольный и ключевой режимы SSH. Ошибка при удалении на
    control-plane не блокирует локальную очистку. Логирование через
    utils.logger.log.
"""

import os, sys, json, subprocess, re, errno
from pathlib import Path

# Пути
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
DATA_DIR = PROJECT_ROOT / "data"
SSH_KEY_PATH = Path.home() / ".ssh" / "ipam-client.key"

# Логгер
sys.path.insert(0, str(PROJECT_ROOT))
from utils.logger import log

SSH_PORT = "3333"
REMOTE_USER = "ipam-client"


def ensure_known_hosts():
    """
    Ensure ~/.ssh and known_hosts exist with secure permissions (EN)
        Creates ~/.ssh (0700) and ~/.ssh/known_hosts (0600) if missing.
        Prevents interactive SSH host key prompts in automated runs.

    Гарантирует наличие ~/.ssh и known_hosts с безопасными правами (RU)
        Создаёт ~/.ssh (0700) и ~/.ssh/known_hosts (0600), если они отсутствуют.
        Исключает интерактивные запросы подтверждения ключа хоста при автоматизации.
    """
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    kh = ssh_dir / "known_hosts"
    if not kh.exists():
        kh.touch(mode=0o600)


def is_valid_private_key(path: Path) -> bool:
    """
    Heuristically validate a private key file (EN)
        Returns True if file exists, is reasonably sized, and contains a known
        PEM header for OpenSSH/RSA/ED25519 keys. Returns False on errors.

    Эвристическая проверка приватного ключа (RU)
        Возвращает True, если файл существует, имеет разумный размер и содержит
        известный PEM-заголовок для ключей OpenSSH/RSA/ED25519. В случае ошибок
        возвращает False.
    """
    try:
        if not path.exists() or path.stat().st_size < 64:
            return False
        head = path.read_text(errors="ignore").strip()
        return ("BEGIN OPENSSH PRIVATE KEY" in head or
                "BEGIN RSA PRIVATE KEY" in head or
                "BEGIN ED25519 PRIVATE KEY" in head)
    except Exception:
        return False


def load_collected_info():
    """
    Load node facts from data/collected_info.py (EN)
        Executes the Python file and extracts HOSTNAME and ROLE.
        Exits on absence. Returns {"hostname": str, "role": str}.

    Загружает факты ноды из data/collected_info.py (RU)
        Исполняет Python-файл и извлекает HOSTNAME и ROLE.
        Завершает работу при отсутствии. Возвращает {"hostname": str, "role": str}.
    """
    file_ = DATA_DIR / "collected_info.py"
    if not file_.exists():
        log("Файл collected_info.py не найден!", "error"); sys.exit(1)
    ns = {}
    exec(file_.read_text(), ns)
    for r in ["HOSTNAME","ROLE"]:
        if r not in ns:
            log(f"Не найден параметр {r} в collected_info.py", "error"); sys.exit(1)
    return {"hostname": ns["HOSTNAME"], "role": ns["ROLE"]}


def load_join_info():
    """
    Load join/control-plane parameters from data/join_info.json (EN)
        Requires CONTROL_PLANE_IP and JOIN_TOKEN. Optionally uses IPAM_PASSWORD
        (defaults to empty string). Returns the parsed dict.

    Загружает параметры присоединения/control-plane из data/join_info.json (RU)
        Требует CONTROL_PLANE_IP и JOIN_TOKEN. Опционально использует IPAM_PASSWORD
        (по умолчанию пустая строка). Возвращает словарь с параметрами.
    """
    jf = DATA_DIR / "join_info.json"
    if not jf.exists():
        log("Файл join_info.json не найден!", "error"); sys.exit(1)
    with open(jf, "r", encoding="utf-8") as f:
        jd = json.load(f)
    for r in ["CONTROL_PLANE_IP","JOIN_TOKEN"]:
        if r not in jd:
            log(f"Не найден параметр {r} в join_info.json", "error"); sys.exit(1)
    jd.setdefault("IPAM_PASSWORD", "")
    return jd


def build_ssh_cmd(host: str, password: str|None, remote_cmd: str) -> list[str]:
    """
    Build SSH command argv for password or key-based auth (EN)
        - Password mode: uses sshpass, no '-i';
        - Key mode     : requires a valid key at SSH_KEY_PATH and uses '-i'.
        Disables strict host key checking for automation.

        Parameters:
            host       : str        - control-plane IP/host
            password   : str|None   - sshpass password or None to use key
            remote_cmd : str        - remote command to execute

        Returns:
            list[str]: argv list suitable for subprocess.run

        Exit behavior:
            Exits(1) if key mode is selected but the key is missing/invalid.

    Формирует argv для SSH с паролем или ключом (RU)
        - Парольный режим: использует sshpass, без '-i';
        - Ключевой режим : требует валидный ключ в SSH_KEY_PATH и использует '-i'.
        Строгая проверка ключа хоста отключена для автоматизации.

        Параметры:
            host       : str        - IP/хост control-plane
            password   : str|None   - пароль для sshpass или None для ключа
            remote_cmd : str        - удалённая команда

        Возвращает:
            list[str]: список аргументов для subprocess.run

        Поведение при ошибке:
            Завершает работу (exit 1), если выбран режим ключа, но ключ отсутствует/повреждён.
    """
    base = ["-p", SSH_PORT,
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null"]
    if password:
        return ["sshpass","-p",password,"ssh",*base,f"{REMOTE_USER}@{host}",remote_cmd]
    else:
        if is_valid_private_key(SSH_KEY_PATH):
            return ["ssh","-i",str(SSH_KEY_PATH),*base,f"{REMOTE_USER}@{host}",remote_cmd]
        log(f"Ключ {SSH_KEY_PATH} отсутствует или повреждён, а IPAM_PASSWORD не задан — нечем аутентифицироваться", "error")
        sys.exit(1)


def unregister_on_cp(cp_ip: str, hostname: str, token: str, password: str|None):
    """
    Unregister the worker node on the control-plane via SSH (EN)
        Executes remote CLI 'delete' with provided hostname and token.
        Logs stderr as warnings (e.g. host key messages). Accepts either a JSON
        response or plain text like 'OK'. Does not raise on failure—continues
        to local cleanup.

        Parameters:
            cp_ip    : str        - control-plane IP
            hostname : str        - worker node hostname to delete
            token    : str        - join/auth token
            password : str|None   - sshpass password or None to use key

    Удаляет регистрацию воркер-ноды на control-plane по SSH (RU)
        Выполняет удалённую CLI-команду 'delete' с указанными hostname и token.
        stderr логируется как предупреждение. Ожидается либо JSON-ответ, либо
        простой текст вроде 'OK'. При ошибке не прерывает процесс — далее будет
        выполнена локальная очистка.
        
        Параметры:
            cp_ip    : str        - IP control-plane
            hostname : str        - имя удаляемой воркер-ноды
            token    : str        - токен аутентификации
            password : str|None   - пароль для sshpass или None для ключа
    """
    REMOTE_DELETE_CMD = f"delete --host 127.0.0.1 --hostname {hostname} --role worker --token {token}"
    cmd = build_ssh_cmd(cp_ip, password, REMOTE_DELETE_CMD)
    log(f"Удаление ноды на control-plane {cp_ip}:{SSH_PORT} ...", "info")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if res.stderr.strip():
            log(f"STDERR: {res.stderr.strip()}", "warn")
        # допустим сервер вернёт JSON или 'OK'
        m = re.search(r"\{.*\}", res.stdout, re.DOTALL)
        if m:
            log("Ответ control-plane: JSON принят", "ok")
        else:
            log(f"Ответ control-plane: {res.stdout.strip() or 'OK'}", "ok")
    except subprocess.CalledProcessError as e:
        log(f"Ошибка при удалении ноды на control-plane: {e}", "warn")
        print("STDOUT:", e.stdout); print("STDERR:", e.stderr)
        # не фейлим весь процесс — продолжим локальную очистку


def local_reset_and_cleanup():
    """
    Perform local kube reset and cleanup of node state (EN)
        - Stop & disable kubelet;
        - kubeadm reset -f;
        - Remove kubelet, CNI, Cilium, and BPF-related paths;
        - Restart containerd;
        - Attempt to unmount /sys/fs/bpf if mounted.

        Notes:
            All steps are best-effort (check=False). Errors are tolerated
            to ensure the cleanup proceeds as far as possible.

    Выполняет локальный сброс и очистку состояния ноды (RU)
        - Останавливает и отключает kubelet;
        - Выполняет kubeadm reset -f;
        - Удаляет пути kubelet, CNI, Cilium и связанные с BPF;
        - Перезапускает containerd;
        - Пытается отмонтировать /sys/fs/bpf, если смонтирован.

        Примечание:
            Все шаги выполняются по принципу best-effort (check=False).
            Ошибки допускаются, чтобы очистка завершилась максимально полно.
    """
    log("Остановка kubelet и локальный reset...", "info")
    subprocess.run(["systemctl","stop","kubelet"], check=False)
    subprocess.run(["systemctl","disable","kubelet"], check=False)
    subprocess.run(["kubeadm","reset","-f"], check=False)

    paths = [
        "/etc/kubernetes",
        "/var/lib/kubelet/pki",
        "/var/lib/kubelet/*",
        "/etc/cni/net.d",
        "/var/lib/cni",
        "/var/run/cni",
        "/var/lib/cilium",
        "/run/cilium",
    ]
    for p in paths:
        subprocess.run(["bash","-lc",f"rm -rf {p}"], check=False)

    # Перезапуск контейнерного рантайма (containerd по умолчанию)
    subprocess.run(["systemctl","restart","containerd"], check=False)

    # На всякий — отмонтировать bpffs, если пустой и смонтирован
    try:
        mounts = Path("/proc/mounts").read_text()
        if "/sys/fs/bpf" in mounts:
            subprocess.run(["umount","/sys/fs/bpf"], check=False)
    except Exception:
        pass

    log("Локальная очистка завершена", "ok")


def main():
    """
    Entry point for worker deletion workflow (EN)
        1) Prepare known_hosts; 2) Load node facts & join info;
        3) Validate role is 'worker';
        4) Clean old SSH hostkey entry for [IP]:PORT;
        5) Attempt remote unregister on control-plane;
        6) Perform local reset & cleanup; 7) Log completion.

    Точка входа рабочего процесса удаления воркер-ноды (RU)
        1) Подготовка known_hosts; 2) Загрузка фактов ноды и join-параметров;
        3) Проверка, что роль — 'worker';
        4) Удаление старого ключа хоста для [IP]:PORT;
        5) Попытка дерегистрации на control-plane;
        6) Локальный reset и очистка; 7) Логирование завершения.
    """
    log("Удаление воркер-ноды...", "warn")
    ensure_known_hosts()
    ci = load_collected_info()
    ji = load_join_info()

    if ci["role"] != "worker":
        log(f"Роль ноды не worker (ROLE={ci['role']}). Прерывание.", "error"); sys.exit(1)

    # подчистим хостключ
    subprocess.run(["ssh-keygen","-R",f"[{ji['CONTROL_PLANE_IP']}]:{SSH_PORT}"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    pw = (ji.get("IPAM_PASSWORD") or "").strip() or None
    unregister_on_cp(ji["CONTROL_PLANE_IP"], ci["hostname"], ji["JOIN_TOKEN"], pw)
    local_reset_and_cleanup()
    log("Готово", "ok")


if __name__ == "__main__":
    main()
