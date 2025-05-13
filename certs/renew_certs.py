import os
import sys

# Добавляем корень проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import subprocess
import fcntl
from datetime import datetime, timedelta
from utils.logger import log
from data.collected_info import IP, HOSTNAME

CERT_INFO_FILE = "certs/cert_info.json"
RENEW_THRESHOLD_DAYS = 30
CERT_DURATION_DAYS = 365
CA_CERT = "/etc/kubernetes/pki/ca.crt"
CA_KEY = "/etc/kubernetes/pki/ca.key"
LOCK_PATH = "/var/lock/renew_certs.lock"

def acquire_lock():
    lockfile = open(LOCK_PATH, 'w')
    try:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lockfile
    except BlockingIOError:
        log("🔒 Другой процесс уже выполняет ротацию сертификатов", "warn")
        sys.exit(0)

def write_openssl_cnf(cn):
    path = f"/tmp/openssl_{cn}.cnf"
    with open(path, "w") as f:
        f.write(f"""
[ req ]
prompt = no
distinguished_name = dn
x509_extensions = v3_req
req_extensions = v3_req

[ dn ]
CN = {cn}

[ v3_req ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = {cn}
DNS.2 = {HOSTNAME}
IP.1 = 127.0.0.1
IP.2 = {IP}
""")
    return path

def get_cert_dates(path):
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
    try:
        cert_mod = subprocess.check_output(["openssl", "x509", "-in", cert_path, "-noout", "-modulus"]).strip()
        key_mod = subprocess.check_output(["openssl", "rsa", "-in", key_path, "-noout", "-modulus"]).strip()
        return cert_mod == key_mod
    except Exception as e:
        log(f"⚠️ Проверка пары ключ+сертификат не удалась: {e}", "warn")
        return False

def renew_certificate(name, path):
    log(f"🔄 Обновление сертификата: {name}", "warn")
    try:
        key_path = path.replace(".crt", ".key")
        csr_path = f"/tmp/{name}.csr"
        cnf_path = write_openssl_cnf(name)

        subprocess.run(["openssl", "genrsa", "-out", key_path, "2048"], check=True)
        subprocess.run(["openssl", "req", "-new", "-key", key_path, "-out", csr_path, "-config", cnf_path], check=True)
        subprocess.run([
            "openssl", "x509", "-req", "-in", csr_path,
            "-CA", CA_CERT, "-CAkey", CA_KEY,
            "-CAcreateserial",
            "-out", path, "-days", str(CERT_DURATION_DAYS),
            "-extensions", "v3_req", "-extfile", cnf_path
        ], check=True)

        os.remove(csr_path)
        os.remove(cnf_path)
        return True
    except subprocess.CalledProcessError as e:
        log(f"❌ Ошибка обновления {name}: {e}", "error")
        return False

def restart_service_if_needed(name):
    if "etcd" in name:
        os.system("systemctl restart etcd")
        log("Перезапущен etcd", "ok")
    elif "apiserver" in name:
        os.system("systemctl restart kube-apiserver")
        log("Перезапущен kube-apiserver", "ok")

def check_and_renew():
    if not os.path.exists(CERT_INFO_FILE):
        log(f"Файл не найден: {CERT_INFO_FILE}", "error")
        return

    with open(CERT_INFO_FILE, "r") as f:
        certs = json.load(f)

    now = datetime.utcnow()
    changed = False

    # Получение срока действия CA
    ca_not_before, ca_not_after = get_cert_dates(CA_CERT)
    if not ca_not_after:
        log("⛔️ CA невалиден, отмена ротации", "error")
        return

    # Получаем срок действия CA из cert_info.json (если есть)
    cert_ca_date_str = certs.get("ca", {}).get("expires_at")
    if cert_ca_date_str:
        try:
            cert_ca_date = datetime.strptime(cert_ca_date_str, "%Y-%m-%dT%H:%M:%SZ")
        except:
            cert_ca_date = ca_not_after
    else:
        log("⚠️ CA не найден в cert_info.json, читаю с диска", "warn")
        cert_ca_date = ca_not_after

    if (ca_not_after - now).days < RENEW_THRESHOLD_DAYS:
        log("⚠️ CA скоро истекает, желательно пересоздать и перегенерировать всё", "warn")

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

        # Проверка подписи
        if cert.get("signed_by") == "ca" and cert_ca_date != ca_not_after:
            log(f"📛 {name}: подписан старым CA, требует регенерации", "warn")
            needs_renewal = True

        if days_left <= 0:
            log(f"⛔️ {name}: срок действия истёк!", "error")
            needs_renewal = True
        elif days_left <= RENEW_THRESHOLD_DAYS:
            log(f"⚠️ {name}: истекает через {days_left} дней", "warn")
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
                log(f"✅ Обновлён: {name}", "ok")
                changed = True
            else:
                log(f"⚠️ Обновлён, но невалиден или не совпадает с ключом: {name}", "warn")

    if changed:
        os.rename(CERT_INFO_FILE, CERT_INFO_FILE + ".bak")
        with open(CERT_INFO_FILE, "w") as f:
            json.dump(certs, f, indent=2)
        log("📘 cert_info.json обновлён", "ok")
    else:
        log("🔄 Все сертификаты в порядке, обновление не требуется", "ok")


if __name__ == "__main__":
    log("=== Проверка и обновление сертификатов ===", "info")
    lock = acquire_lock()
    check_and_renew()
