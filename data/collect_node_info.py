# collect_node_info.py

<<<<<<< HEAD
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import socket
import platform
from utils.logger import log
=======
"""
Collects node information and optionally appends control-plane bootstrap parameters.
Настраивает пользователя ipam-client и доступ только на node_intake_client.py.
"""

import os
import re
import sys
import random
import socket
import tempfile
import platform
import subprocess
import argparse
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log
from jinja2 import Environment, FileSystemLoader
>>>>>>> origin/test

OUTPUT_FILE = "data/collected_info.py"
CLUSTER_POD_CIDR = "10.244.0.0/16"

<<<<<<< HEAD
def get_ip():
    """Получает внешний IP-адрес через сокет без внешних запросов"""
=======
WRAPPER_PATH = "/opt/kuber-bootstrap/cluster/intake_services/ssh_wrapper.sh"
RESTRICTED_CMD = f"/usr/bin/bash {WRAPPER_PATH}"
NODE_CLIENT_PATH = "/opt/kuber-bootstrap/cluster/intake_services/node_intake_client.py"


def update_collected_info(new_values: dict):
    """
    Safely update collected_info.py with only changed values.
    Безопасно обновляет collected_info.py, изменяя только обновлённые значения.
    """
    current_values = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r") as f:
            for line in f:
                if "=" in line:
                    k, v = line.split("=", 1)
                    current_values[k.strip()] = v.strip().strip('"')

    changed = False
    for key, new_val in new_values.items():
        old_val = current_values.get(key)
        if old_val != new_val:
            current_values[key] = new_val
            changed = True

    if not changed:
        log("Нет изменений в collected_info.py, перезапись не требуется", "info")
        return

    with open(OUTPUT_FILE, "w") as f:
        for k, v in current_values.items():
            f.write(f'{k} = "{v}"\n\n')

    log("collected_info.py обновлён с новыми изменениями", "ok")


def get_ip():
    """
    Get the external IP address using a dummy UDP connection.
    Получает внешний IP-адрес через фиктивное UDP-соединение.
    """
>>>>>>> origin/test
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
<<<<<<< HEAD
        log(f"Не удалось определить IP-адрес: {e}", "error")
        return "127.0.0.1"

def collect_info(role="control-plane"):
    log("Сбор данных о машине...", "info")

    if role not in ["control-plane", "worker"]:
        log("Недопустимая роль. Используйте: control-plane или worker", "error")
        sys.exit(1)

    role_description = "Управляющий (control-plane)" if role == "control-plane" else "Рабочий (worker)"
    log(f"Узел будет настроен как: {role_description}", "info")

    cidr = "24" if role == "control-plane" else "24"

    info = {
        "IP": get_ip(),
        "HOSTNAME": socket.gethostname(),
        "ARCH": platform.machine(),
        "DISTRO": platform.linux_distribution()[0] if hasattr(platform, 'linux_distribution') else platform.system(),
        "KERNEL": platform.release(),
        "ROLE": role,
        "CIDR": cidr,
        "CLUSTER_POD_CIDR": CLUSTER_POD_CIDR
    }

    with open(OUTPUT_FILE, "w") as f:
        for key, value in info.items():
            f.write(f'{key} = "{value}"\n')

    log(f"Данные сохранены в {OUTPUT_FILE}", "ok")

if __name__ == "__main__":
    if len(sys.argv) == 2:
        role_arg = sys.argv[1].strip().lower()
    else:
        role_arg = "control-plane"
        log("Аргумент роли не указан, использую по умолчанию: control-plane", "warn")

    collect_info(role=role_arg)
=======
        log(f"Не удалось определить IP: {e}", "error")
        return "127.0.0.1"


def generate_token_string():
    """
    Generate a kubeadm-compatible bootstrap token.
    Генерирует bootstrap-токен, совместимый с kubeadm.
    """

    def rand_block(length):
        return ''.join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=length))
    return f"{rand_block(6)}.{rand_block(16)}"


def get_join_token():
    """
    Create and apply a kubeadm bootstrap token via Jinja2 template.
    Создаёт bootstrap-токен через шаблон Jinja2 и применяет его с помощью kubeadm.
    """
    token = generate_token_string()
    template_path = os.path.join("data", "yaml")
    template_name = "bootstrap-token.yaml.j2"

    try:
        env = Environment(loader=FileSystemLoader(template_path))
        template = env.get_template(template_name)
    except Exception as e:
        log(f"Ошибка загрузки шаблона bootstrap-token.yaml.j2: {e}", "error")
        sys.exit(1)

    rendered = template.render(TOKEN=token)

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yaml") as tmpfile:
        tmpfile.write(rendered)
        tmpfile.flush()
        subprocess.run(
            ["kubeadm", "init", "phase", "bootstrap-token", f"--config={tmpfile.name}"],
            check=True
        )
        log(f"Создан токен: {token}", "ok")

    return token


def ensure_ipam_user(username="ipam-client"):
    """
    Ensure that the ipam-client user exists and has a valid shell.
    Гарантирует, что пользователь ipam-client существует и имеет корректный shell.
    Если shell = nologin, меняет на /bin/bash (иначе ForceCommand не выполнится).
    """
    try:
        subprocess.run(["id", "-u", username], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log(f"Пользователь {username} уже существует", "info")

        shell = subprocess.check_output(["getent", "passwd", username], text=True).split(":")[-1].strip()
        if shell.endswith("nologin"):
            log(f"Меняем shell {username} с nologin на /bin/bash (нужно для ForceCommand)", "warn")
            subprocess.run(["chsh", "-s", "/bin/bash", username], check=True)
            log("Shell изменён на /bin/bash", "ok")

    except subprocess.CalledProcessError:
        log(f"Создаём пользователя {username}", "warn")
        subprocess.run(["useradd", "-m", "-s", "/bin/bash", username], check=True)
        log(f"Создан системный пользователь {username} с shell /bin/bash", "ok")


def create_ssh_wrapper():
    """
    Create ssh_wrapper.sh to run only node_intake_client.py via ForceCommand.
    Создаёт ssh_wrapper.sh, чтобы через ForceCommand выполнялся только node_intake_client.py.
    """
    wrapper_content = f"""#!/bin/bash
# Принудительный запуск node_intake_client.py с аргументами SSH
exec /usr/bin/python3 {NODE_CLIENT_PATH} $SSH_ORIGINAL_COMMAND
"""
    with open(WRAPPER_PATH, "w") as f:
        f.write(wrapper_content)

    subprocess.run(["chmod", "+x", WRAPPER_PATH], check=True)
    subprocess.run(["chown", "root:root", WRAPPER_PATH], check=True)
    log(f"Создан ssh-wrapper: {WRAPPER_PATH}", "ok")


def ensure_control_plane_ssh_key(username="ipam-client"):
    """
    Generate SSH keys for ipam-client and rewrite authorized_keys securely.
    Генерирует SSH-ключи для ipam-client и безопасно перезаписывает authorized_keys.

    Removes all old entries for this key and leaves only one correct entry with ForceCommand.
    Удаляет все старые записи для этого ключа и оставляет только одну корректную с ForceCommand.

    Also verifies/creates sshd_config.d/ipam-client.conf with Match User + ForceCommand.
    Также проверяет/создаёт sshd_config.d/ipam-client.conf с Match User + ForceCommand.
    """
    home_dir = f"/home/{username}"
    ssh_dir = Path(home_dir) / ".ssh"
    ssh_key_path = ssh_dir / "id_rsa"
    ssh_pub_path = ssh_dir / "id_rsa.pub"
    auth_keys = ssh_dir / "authorized_keys"

    ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    subprocess.run(["chown", "-R", f"{username}:{username}", ssh_dir], check=True)

    if not ssh_key_path.exists() or not ssh_pub_path.exists():
        log(f"Генерируем SSH ключи для {username}", "warn")
        subprocess.run(
            ["sudo", "-u", username, "ssh-keygen", "-t", "rsa", "-b", "4096", "-f", str(ssh_key_path), "-N", ""],
            check=True
        )
        log(f"Ключ создан: {ssh_key_path}", "ok")

    pub_key_content = ssh_pub_path.read_text().strip()

    forced_entry = (
        f'command="{RESTRICTED_CMD}",'
        "no-agent-forwarding,no-user-rc,no-X11-forwarding,no-port-forwarding "
        f"{pub_key_content}"
    )

    existing_lines = auth_keys.read_text().splitlines() if auth_keys.exists() else []
    cleaned = [line for line in existing_lines if pub_key_content not in line]
    cleaned.append(forced_entry)

    with open(auth_keys, "w") as ak:
        ak.write("\n".join(cleaned) + "\n")

    subprocess.run(["chown", f"{username}:{username}", auth_keys], check=True)
    subprocess.run(["chmod", "600", auth_keys], check=True)
    log("authorized_keys обновлён: осталась только одна запись с wrapper", "ok")

    sshd_match_conf = "/etc/ssh/sshd_config.d/ipam-client.conf"
    match_block = f"""Match User {username}
    ForceCommand {RESTRICTED_CMD}
    AllowTcpForwarding no
    X11Forwarding no
    PermitTTY no
"""

    need_update = True
    if os.path.exists(sshd_match_conf):
        with open(sshd_match_conf) as f:
            if match_block.strip() == f.read().strip():
                need_update = False

    if need_update:
        log("Обновляем sshd_config.d/ipam-client.conf", "warn")
        with open(sshd_match_conf, "w") as f:
            f.write(match_block)
        subprocess.run(["sshd", "-t"], check=True)
        subprocess.run(["systemctl", "restart", "ssh"], check=True)
        log("sshd перезапущен с ForceCommand для ipam-client", "ok")
    else:
        log("ForceCommand уже настроен в sshd_config.d, перезапуск не требуется", "info")

    return pub_key_content


def get_discovery_hash():
    """
    Get sha256 discovery hash of the Kubernetes CA certificate.
    Получает sha256-хеш сертификата CA Kubernetes.
    """
    pubkey_cmd = ["openssl", "x509", "-pubkey", "-in", "/etc/kubernetes/pki/ca.crt"]
    rsa_cmd = ["openssl", "rsa", "-pubin", "-outform", "der"]
    sha_cmd = ["sha256sum"]

    pubkey_proc = subprocess.Popen(pubkey_cmd, stdout=subprocess.PIPE)
    rsa_proc = subprocess.Popen(rsa_cmd, stdin=pubkey_proc.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    pubkey_proc.stdout.close()
    sha_proc = subprocess.Popen(sha_cmd, stdin=rsa_proc.stdout, stdout=subprocess.PIPE)
    rsa_proc.stdout.close()

    output, _ = sha_proc.communicate()
    return "sha256:" + output.decode().split()[0]


def get_ca_cert_base64():
    """
    Return the CA certificate content in base64 encoding.
    Возвращает содержимое CA-сертификата в кодировке base64.
    """
    return subprocess.check_output(["base64", "-w", "0", "/etc/kubernetes/pki/ca.crt"], text=True).strip()


def read_existing_role():
    """
    Read the node role (control-plane or worker) from collected_info.py.
    Считывает роль узла (control-plane или worker) из файла collected_info.py.
    """
    try:
        with open(OUTPUT_FILE, "r") as f:
            for line in f:
                if line.startswith("ROLE"):
                    return line.split("=")[1].strip().strip('"')
    except Exception as e:
        log(f"Не удалось прочитать роль: {e}", "error")
    return None


def collect_info(role="control-plane"):
    """
    Collect basic node information (IP, hostname, architecture, etc.) and save to collected_info.py.
    Собирает базовую информацию об узле (IP, hostname, архитектуру и т.д.) и сохраняет в collected_info.py.
    """
    log("Сбор данных о ноде...", "info")
    if role not in ["control-plane", "worker"]:
        log("Недопустимая роль", "error")
        sys.exit(1)

    update_collected_info({
        "IP": get_ip(),
        "HOSTNAME": socket.gethostname(),
        "ARCH": platform.machine(),
        "DISTRO": platform.system(),
        "KERNEL": platform.release(),
        "ROLE": role,
        "CIDR": "24",
        "CLUSTER_POD_CIDR": CLUSTER_POD_CIDR
    })


def append_control_plane_bootstrap():
    """
    Append control-plane bootstrap parameters (join token, discovery hash, CA cert, SSH key).
    Добавляет параметры bootstrap для control-plane (join token, discovery hash, CA-сертификат, SSH-ключ).
    Only allowed on control-plane nodes.
    Доступно только на control-plane узлах.
    """
    role = read_existing_role()
    if role != "control-plane":
        log("Только control-plane может использовать -cpb", "error")
        sys.exit(1)

    log("Настройка подключения воркеров...", "info")

    ensure_ipam_user("ipam-client")
    create_ssh_wrapper()
    ssh_pubkey = ensure_control_plane_ssh_key("ipam-client")

    token = get_join_token()
    hash_ = get_discovery_hash()
    ca_cert = get_ca_cert_base64()

    update_collected_info({
        "JOIN_TOKEN": token,
        "DISCOVERY_HASH": hash_,
        "CA_CERT_BASE64": ca_cert,
        "CONTROL_PLANE_SSH_PUBKEY": ssh_pubkey
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect node info and optionally add bootstrap data")
    parser.add_argument("role", nargs="?", default=None, help="Роль узла: control-plane или worker")
    parser.add_argument("-cpb", action="store_true", help="Добавить токен и хеш, если роль control-plane")

    args = parser.parse_args()

    if args.cpb:
        append_control_plane_bootstrap()
    else:
        role_arg = args.role.lower() if args.role else "control-plane"
        if not args.role:
            log("Роль не указана, по умолчанию control-plane", "warn")
        collect_info(role=role_arg)
>>>>>>> origin/test
