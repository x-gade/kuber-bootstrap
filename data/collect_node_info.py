# collect_node_info.py

"""
Collects node information and optionally appends control-plane bootstrap parameters.
Собирает информацию об узле и при необходимости добавляет параметры для подключения воркеров.
"""

import os
import re
import sys
import yaml
import uuid
import string
import random
import socket
import tempfile
import platform
import subprocess
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log
from jinja2 import Environment, FileSystemLoader

OUTPUT_FILE = "data/collected_info.py"
CLUSTER_POD_CIDR = "10.244.0.0/16"


def get_ip():
    """
    Returns external IP address by opening a dummy UDP connection.
    Получает внешний IP-адрес через фиктивное UDP-соединение.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        log(f"Не удалось определить IP-адрес: {e}", "error")
        return "127.0.0.1"

def generate_token_string():
    """
    Generates a random kubeadm-compatible token (lowercase alphanum).
    Генерирует случайный токен, совместимый с kubeadm.
    """
    def rand_block(length):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return f"{rand_block(6)}.{rand_block(16)}"

def get_join_token():
    """
    Creates a bootstrap token with proper rights via Jinja2 template and returns it.
    Создаёт bootstrap-токен с нужными правами через шаблон Jinja2 и возвращает его.
    """
    token = generate_token_string()

    # Путь к шаблону
    template_path = os.path.join("data", "yaml")
    template_name = "bootstrap-token.yaml.j2"

    try:
        env = Environment(loader=FileSystemLoader(template_path))
        template = env.get_template(template_name)
    except Exception as e:
        log(f"Ошибка загрузки шаблона bootstrap-token.yaml.j2: {e}", "error")
        sys.exit(1)

    # Рендерим шаблон с токеном
    rendered = template.render(TOKEN=token)

    # Сохраняем во временный файл
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yaml") as tmpfile:
        tmpfile.write(rendered)
        tmpfile.flush()
        try:
            subprocess.run(
                ["kubeadm", "init", "phase", "bootstrap-token", f"--config={tmpfile.name}"],
                check=True
            )
            log(f"Создан токен с правами через шаблон: {token}", "ok")
        except subprocess.CalledProcessError as e:
            log(f"Ошибка при применении манифеста токена: {e}", "error")
            sys.exit(1)

    return token

def get_discovery_hash():
    """
    Returns sha256 discovery hash from the CA public key.
    Возвращает хеш sha256 от публичного ключа CA.
    """
    pubkey_cmd = [
        "openssl", "x509", "-pubkey", "-in", "/etc/kubernetes/pki/ca.crt"
    ]
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
    Returns base64-encoded content of the CA certificate.
    Возвращает содержимое сертификата CA в base64-формате.
    """
    output = subprocess.check_output(["base64", "-w", "0", "/etc/kubernetes/pki/ca.crt"], text=True)
    return output.strip()


def read_existing_role():
    """
    Reads the role from an existing collected_info.py.
    Читает роль из ранее собранного collected_info.py.
    """
    try:
        with open(OUTPUT_FILE, "r") as f:
            for line in f:
                if line.startswith("ROLE"):
                    return line.split("=")[1].strip().strip('"')
    except Exception as e:
        log(f"Не удалось прочитать роль из {OUTPUT_FILE}: {e}", "error")
    return None


def collect_info(role="control-plane"):
    """
    Collects basic node information and writes it to collected_info.py.
    Собирает базовую информацию об узле и сохраняет её в collected_info.py.
    """
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


def append_control_plane_bootstrap():
    """
    Appends or replaces join token, discovery hash and CA cert in collected_info.py
    Добавляет или заменяет токен, хеш и CA-сертификат в collected_info.py
    """
    role = read_existing_role()
    if role != "control-plane":
        log("Флаг -cpb доступен только на управляющем узле (control-plane)", "error")
        sys.exit(1)

    log("Добавление параметров подключения воркеров в collected_info.py...", "info")

    token = get_join_token()
    hash_ = get_discovery_hash()
    ca_cert = get_ca_cert_base64()

    # Читаем весь файл
    try:
        with open(OUTPUT_FILE, "r") as f:
            content = f.read()
    except Exception as e:
        log(f"Ошибка чтения {OUTPUT_FILE}: {e}", "error")
        sys.exit(1)

    # Удаляем старые строки
    content = re.sub(r'\n?JOIN_TOKEN\s*=\s*.*?\n', '', content)
    content = re.sub(r'\n?DISCOVERY_HASH\s*=\s*.*?\n', '', content)
    content = re.sub(r'\n?CA_CERT_BASE64\s*=\s*.*?\n', '', content)

    # Экранируем кавычки и вставляем новые строки
    new_data = (
        f'\nJOIN_TOKEN = "{token}"\n'
        f'DISCOVERY_HASH = "{hash_}"\n'
        f'CA_CERT_BASE64 = "{ca_cert}"\n'
    )

    try:
        with open(OUTPUT_FILE, "w") as f:
            f.write(content.strip() + "\n" + new_data)
    except Exception as e:
        log(f"Ошибка записи в {OUTPUT_FILE}: {e}", "error")
        sys.exit(1)

    log("Параметры подключения успешно обновлены", "ok")


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
            log("Аргумент роли не указан, использую по умолчанию: control-plane", "warn")
        collect_info(role=role_arg)
