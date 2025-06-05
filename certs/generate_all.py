import os
import sys
import json
import subprocess
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data.collected_info import IP, HOSTNAME

PKI_DIR = "/etc/kubernetes/pki"
ETCD_DIR = f"{PKI_DIR}/etcd"
CERT_INFO_FILE = "certs/cert_info.json"
CA_CERT = f"{PKI_DIR}/ca.crt"
CA_KEY = f"{PKI_DIR}/ca.key"
CA_SERIAL = f"{PKI_DIR}/ca.srl"
CERT_DURATION_DAYS = 365
CA_DURATION_DAYS = 3650
SERVICE_NAME = "kube-cert-renew"
SYSTEMD_DIR = "/etc/systemd/system"
RENEW_SCRIPT = "/opt/kuber-bootstrap/certs/renew_certs.py"

os.makedirs(ETCD_DIR, exist_ok=True)
os.makedirs("/var/lib/kubelet/pki", exist_ok=True)
cert_info = {}
now = datetime.utcnow()

def run(cmd, msg=None):
    try:
        subprocess.run(cmd, check=True)
        if msg:
            log(msg, "ok")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Ошибка: {e}", "error")
        return False

def write_openssl_cnf(cn, client_cert=False):
    path = f"/tmp/openssl_{cn.replace(':', '_')}.cnf"
    dns_names = [cn, HOSTNAME]
    ip_addresses = [IP]

    if "apiserver" in cn:
        dns_names += [
            "kubernetes", "kubernetes.default", "kubernetes.default.svc",
            "kubernetes.default.svc.cluster.local"
        ]
        ip_addresses += ["127.0.0.1", "10.96.0.1"]

    if "etcd" in cn:
        dns_names.append("localhost")
        ip_addresses.append("127.0.0.1")

    dns_names = list(dict.fromkeys(dns_names))
    ip_addresses = list(dict.fromkeys(ip_addresses))

    with open(path, "w") as f:
        f.write(f"""
[ req ]
prompt = no
distinguished_name = dn
req_extensions = v3_req
x509_extensions = v3_req

[ dn ]
CN = {cn}
""")
        if cn.startswith("system:node:"):
            f.write("O = system:nodes\n")
        elif cn == "kubernetes-admin":
            f.write("O = system:masters\n")
        f.write("""
[ v3_req ]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = clientAuth, serverAuth
""")
        if dns_names or ip_addresses:
            f.write("subjectAltName = @alt_names\n\n[ alt_names ]\n")
            for i, name in enumerate(dns_names):
                f.write(f"DNS.{i+1} = {name}\n")
            for i, addr in enumerate(ip_addresses):
                f.write(f"IP.{i+1} = {addr}\n")

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
        log(f"Проверка пары ключ+сертификат не удалась: {e}", "warn")
        return False

def generate_ca():
    if os.path.exists(CA_CERT):
        not_before, not_after = get_cert_dates(CA_CERT)
        if not_after and (not_after - now).days < 30:
            log("CA скоро истекает!", "warn")
        return

    log("Генерация корневого CA", "warn")
    run([
        "openssl", "req", "-x509", "-newkey", "rsa:4096", "-nodes",
        "-keyout", CA_KEY, "-out", CA_CERT,
        "-days", str(CA_DURATION_DAYS),
        "-subj", "/CN=kubernetes-ca"
    ])
    cert_info["ca"] = {
        "path": CA_CERT,
        "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (now + timedelta(days=CA_DURATION_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    }

def generate_cert(name, cn, path, key_path, etcd=False, dry_run=False, client_cert=False):
    if os.path.exists(path):
        not_before, not_after = get_cert_dates(path)
        if not_before and not_after:
            cert_info[name] = {
                "path": path,
                "created_at": not_before.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "expires_at": not_after.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "signed_by": "ca"
            }
        else:
            log(f"Не удалось прочитать даты у {name}, возможно, повреждён", "warn")
        return

    log(f"Генерация сертификата: {name}", "warn")
    csr_path = f"/tmp/{name.replace(':', '_')}.csr"
    cnf_path = write_openssl_cnf(cn, client_cert=client_cert)

    run(["openssl", "genrsa", "-out", key_path, "2048"])
    run(["openssl", "req", "-new", "-key", key_path, "-out", csr_path, "-config", cnf_path])
    run([
        "openssl", "x509", "-req", "-in", csr_path,
        "-CA", CA_CERT, "-CAkey", CA_KEY,
        "-CAcreateserial", "-out", path,
        "-days", str(CERT_DURATION_DAYS),
        "-extensions", "v3_req", "-extfile", cnf_path
    ])

    not_before, not_after = get_cert_dates(path)
    if validate_key_pair(path, key_path):
        cert_info[name] = {
            "path": path,
            "created_at": not_before.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expires_at": not_after.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "signed_by": "ca"
        }
    else:
        log(f"Несовпадение ключа и сертификата для {name}", "error")

    os.remove(csr_path)
    os.remove(cnf_path)

def generate_sa_keys(force=False):
    sa_key = f"{PKI_DIR}/sa.key"
    sa_pub = f"{PKI_DIR}/sa.pub"

    if force or not os.path.exists(sa_key):
        run(["openssl", "genrsa", "-out", sa_key, "2048"])
        log("sa.key создан", "ok")
    else:
        log("sa.key уже существует", "info")

    if force or not os.path.exists(sa_pub):
        run(["openssl", "rsa", "-in", sa_key, "-pubout", "-out", sa_pub])
        log("sa.pub создан", "ok")
    else:
        log("sa.pub уже существует", "info")

    cert_info["sa"] = {
        "path": sa_key,
        "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": "n/a"
    }

def create_service_file():
    service_file = f"{SYSTEMD_DIR}/{SERVICE_NAME}.service"
    content = f"""[Unit]
Description=Kubernetes certificate auto-renew

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 {RENEW_SCRIPT}
"""
    with open(service_file, "w") as f:
        f.write(content)
    log(f"Создан systemd unit: {service_file}", "ok")

def create_timer_file():
    timer_file = f"{SYSTEMD_DIR}/{SERVICE_NAME}.timer"
    content = f"""[Unit]
Description=Run Kubernetes cert check daily

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
"""
    with open(timer_file, "w") as f:
        f.write(content)
    log(f"Создан systemd таймер: {timer_file}", "ok")

def enable_timer():
    os.system("systemctl daemon-reexec")
    os.system("systemctl daemon-reload")
    os.system(f"systemctl enable --now {SERVICE_NAME}.timer")
    log(f"Таймер активирован: {SERVICE_NAME}", "ok")

def restart_tls_services():
    services = ["kube-apiserver", "etcd"]
    for service in services:
        result = subprocess.run(["systemctl", "is-active", service], stdout=subprocess.DEVNULL)
        if result.returncode == 0:
            log(f"Перезапуск TLS-сервиса: {service}", "info")
            subprocess.run(["sleep", "2"])
            subprocess.run(["systemctl", "restart", service])
        else:
            log(f"Сервис {service} не запущен — пропускаем", "warn")

def main():
    rotate_sa = "--rotate-sa" in sys.argv
    dry_run = "--dry-run" in sys.argv

    generate_ca()

    certs = {
        "apiserver": f"{PKI_DIR}/apiserver",
        "apiserver-kubelet-client": f"{PKI_DIR}/apiserver-kubelet-client",
        "apiserver-etcd-client": f"{PKI_DIR}/apiserver-etcd-client",
        "etcd-server": f"{ETCD_DIR}/server",
        "etcd-peer": f"{ETCD_DIR}/peer",
        "etcd-healthcheck": f"{ETCD_DIR}/healthcheck-client",
        "front-proxy-client": f"{PKI_DIR}/front-proxy-client",
        "front-proxy-ca": f"{PKI_DIR}/front-proxy-ca",
        "admin": f"{PKI_DIR}/admin"
    }

    for name, base in certs.items():
        generate_cert(
            name=name,
            cn="kubernetes-admin" if name == "admin" else name,
            path=f"{base}.crt",
            key_path=f"{base}.key",
            etcd="etcd" in name,
            dry_run=dry_run,
            client_cert=(name == "admin")
        )

    generate_cert(
        name="kubelet-client",
        cn=f"system:node:{HOSTNAME}",
        path=f"{PKI_DIR}/kubelet-client.crt",
        key_path=f"{PKI_DIR}/kubelet-client.key",
        dry_run=dry_run,
        client_cert=True
    )

    generate_sa_keys(force=rotate_sa)

    if not dry_run:
        if os.path.exists(CERT_INFO_FILE):
            os.rename(CERT_INFO_FILE, CERT_INFO_FILE + ".bak")

        with open(CERT_INFO_FILE, "w") as f:
            json.dump(cert_info, f, indent=2)
        log("Сертификаты успешно созданы и зафиксированы", "ok")

        create_service_file()
        create_timer_file()
        enable_timer()
        restart_tls_services()
    else:
        log("dry-run: cert_info.json и systemd не затронуты", "warn")

if __name__ == "__main__":
    main()
