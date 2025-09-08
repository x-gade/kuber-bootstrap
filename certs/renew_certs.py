#!/usr/bin/env python3
"""
Renew expiring Kubernetes TLS certificates via generate_all.py functions.
Обновляет истекающие TLS-сертификаты Kubernetes через функции generate_all.py.
"""

import os
import sys
import json
import fcntl
import subprocess
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data.collected_info import IP, HOSTNAME

from certs.generate_all import (
    generate_cert,
    generate_cilium_cert,
    generate_webhook_cert,
    generate_sa_keys
)

# === Константы ===
CERT_INFO_FILE = "certs/cert_info.json"
RENEW_THRESHOLD_DAYS = 30
CERT_DURATION_DAYS = 365
CA_CERT = "/etc/kubernetes/pki/ca.crt"
CA_KEY = "/etc/kubernetes/pki/ca.key"
LOCK_PATH = "/var/lock/renew_certs.lock"

def acquire_lock():
    """
    Prevent concurrent execution via file lock.
    Предотвращает параллельный запуск через файловую блокировку.
    """
    lockfile = open(LOCK_PATH, 'w')
    try:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lockfile
    except BlockingIOError:
        log("🔒 Другой процесс уже выполняет ротацию сертификатов", "warn")
        sys.exit(0)

def get_cert_dates(path):
    """
    Return notBefore and notAfter dates of a certificate.
    Возвращает даты начала и окончания действия сертификата.
    """
    try:
        out = subprocess.check_output(["openssl", "x509", "-in", path, "-noout", "-dates"]).decode()
        lines = dict(line.split("=", 1) for line in out.strip().splitlines())
        not_before = datetime.strptime(lines["notBefore"], "%b %d %H:%M:%S %Y %Z")
        not_after = datetime.strptime(lines["notAfter"], "%b %d %H:%M:%S %Y %Z")
        return not_before, not_after
    except Exception as e:
        log(f"Не удалось прочитать даты из {path}: {e}", "error")
        return None, None

def validate_key_pair(cert_path, key_path):
    """
    Ensure certificate and key form a valid pair.
    Проверяет, соответствуют ли сертификат и ключ.
    """
    try:
        cert_mod = subprocess.check_output(["openssl", "x509", "-in", cert_path, "-noout", "-modulus"]).strip()
        key_mod = subprocess.check_output(["openssl", "rsa", "-in", key_path, "-noout", "-modulus"]).strip()
        return cert_mod == key_mod
    except Exception as e:
        log(f"Проверка пары ключ+сертификат не удалась: {e}", "warn")
        return False

def renew_certificate(name, path):
<<<<<<< HEAD
    log(f"Обновление сертификата: {name}", "warn")
    try:
        key_path = path.replace(".crt", ".key")
        csr_path = f"/tmp/{name}.csr"
        cnf_path = write_openssl_cnf(name)
=======
    """
    Renew a certificate using corresponding generator.
    Обновляет сертификат через соответствующую функцию генерации.
    """
    log(f"Обновление сертификата: {name}", "warn")
>>>>>>> origin/test

    key_path = path.replace(".crt", ".key")

    if name == "cilium":
        generate_cilium_cert()
        return True
<<<<<<< HEAD
    except subprocess.CalledProcessError as e:
        log(f"Ошибка обновления {name}: {e}", "error")
        return False
=======
    elif name == "sa":
        generate_sa_keys(force=True)
        return True
    elif name == "cilium-webhook":
        generate_webhook_cert()
        return True
    elif name == "kubelet-client":
        return generate_cert(
            name=name,
            cn=f"system:node:{HOSTNAME}",
            path=path,
            key_path=key_path,
            client_cert=True
        )
    elif name == "admin":
        return generate_cert(
            name=name,
            cn="kubernetes-admin",
            path=path,
            key_path=key_path,
            client_cert=True
        )
    else:
        return generate_cert(
            name=name,
            cn=name,
            path=path,
            key_path=key_path
        )
>>>>>>> origin/test

def restart_service_if_needed(name):
    """
    Restart services affected by renewed certs.
    Перезапускает сервисы, использующие TLS-сертификаты.
    """
    if "etcd" in name:
        os.system("systemctl restart etcd")
        log("Перезапущен etcd", "ok")
    elif "apiserver" in name:
        os.system("systemctl restart kube-apiserver")
        log("Перезапущен kube-apiserver", "ok")

def check_and_renew():
    """
    Main logic for checking and renewing certificates.
    Основная логика проверки и ротации сертификатов.
    """
    if not os.path.exists(CERT_INFO_FILE):
        log(f"Файл не найден: {CERT_INFO_FILE}", "error")
        return

    with open(CERT_INFO_FILE, "r") as f:
        certs = json.load(f)

    now = datetime.utcnow()
    changed = False

    # === Проверка CA ===
    ca_not_before, ca_not_after = get_cert_dates(CA_CERT)
    if not ca_not_after:
        log("CA невалиден, отмена ротации", "error")
        return

    cert_ca_date_str = certs.get("ca", {}).get("expires_at")
    if cert_ca_date_str:
        try:
            cert_ca_date = datetime.strptime(cert_ca_date_str, "%Y-%m-%dT%H:%M:%SZ")
        except:
            cert_ca_date = ca_not_after
    else:
        log("CA не найден в cert_info.json, читаю с диска", "warn")
        cert_ca_date = ca_not_after

    if (ca_not_after - now).days < RENEW_THRESHOLD_DAYS:
        log("CA скоро истекает, желательно пересоздать и перегенерировать всё", "warn")

    for name, cert in certs.items():
        if cert.get("expires_at") == "n/a":
            log(f"{name}: без срока действия", "info")
            continue

        needs_renewal = False
        try:
            expires = datetime.strptime(cert["expires_at"], "%Y-%m-%dT%H:%M:%SZ")
            days_left = (expires - now).days
        except Exception:
            _, expires = get_cert_dates(cert["path"])
            days_left = (expires - now).days if expires else -1

        if cert.get("signed_by") == "ca" and cert_ca_date != ca_not_after:
            log(f"{name}: подписан старым CA, требует регенерации", "warn")
            needs_renewal = True

        if days_left <= 0:
            log(f"{name}: срок действия истёк!", "error")
            needs_renewal = True
        elif days_left <= RENEW_THRESHOLD_DAYS:
            log(f"{name}: истекает через {days_left} дней", "warn")
            needs_renewal = True
        else:
            log(f"{name}: истекает через {days_left} дней", "info")

        if not needs_renewal:
            continue

        if renew_certificate(name, cert["path"]):
            new_from, new_to = get_cert_dates(cert["path"])
            key_path = cert["path"].replace(".crt", ".key")
            if new_from and new_to and validate_key_pair(cert["path"], key_path):
                cert["created_at"] = new_from.strftime("%Y-%m-%dT%H:%M:%SZ")
                cert["expires_at"] = new_to.strftime("%Y-%m-%dT%H:%M:%SZ")
                cert["signed_by"] = "ca"
                restart_service_if_needed(name)
                log(f"Обновлён: {name}", "ok")
                changed = True
            else:
                log(f"Обновлён, но невалиден или не совпадает с ключом: {name}", "warn")

    if changed:
        os.rename(CERT_INFO_FILE, CERT_INFO_FILE + ".bak")
        with open(CERT_INFO_FILE, "w") as f:
            json.dump(certs, f, indent=2)
        log("cert_info.json обновлён", "ok")
    else:
        log("Все сертификаты в порядке, обновление не требуется", "ok")
<<<<<<< HEAD

=======
>>>>>>> origin/test

if __name__ == "__main__":
    """
    Entry point for cert renewal script.
    Точка входа скрипта проверки и обновления TLS-сертификатов.
    """
    log("=== Проверка и обновление сертификатов ===", "info")
    lock = acquire_lock()
    check_and_renew()
