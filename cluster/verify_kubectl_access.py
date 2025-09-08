# cluster/verify_kubectl_access.py

import os
import subprocess
import sys

from utils.logger import log

KUBECONFIG_PATH = "/etc/kubernetes/admin.conf"
CA_CERT = "/etc/kubernetes/pki/ca.crt"
ADMIN_CERT = "/etc/kubernetes/pki/admin.crt"

def run(cmd, capture_output=True):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture_output, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return e.stderr.strip() if capture_output else None

def verify_cert_chain():
    log("Проверка: admin.crt доверен ca.crt...", "info")
    result = run(f"openssl verify -CAfile {CA_CERT} {ADMIN_CERT}")
    if result.endswith(": OK"):
        log("Сертификат admin.crt подписан ca.crt", "ok")
        return True
    else:
        log(f"Ошибка проверки: {result}", "error")
        return False

def ensure_kubeconfig_env():
    current = os.environ.get("KUBECONFIG")
    if current != KUBECONFIG_PATH:
        log(f"KUBECONFIG не установлен или некорректен: {current}", "warn")
        os.environ["KUBECONFIG"] = KUBECONFIG_PATH
        log(f"KUBECONFIG установлен в {KUBECONFIG_PATH}", "ok")
    else:
        log("KUBECONFIG уже корректен", "ok")

def test_kubectl():
    log("Пробуем kubectl get nodes...", "info")
    output = run("kubectl get nodes", capture_output=True)
    if "NAME" in output:
        log("kubectl работает корректно!", "ok")
        log(output, "info")
    else:
        log(f"kubectl не может подключиться: {output}", "error")

def ensure_rbac():
    log("Проверка прав пользователя kubernetes-admin...", "info")
    output = run("kubectl auth can-i get nodes --as kubernetes-admin")
    if output == "yes":
        log("Права уже есть — всё ок", "ok")
    else:
        log("Добавляем права через ClusterRoleBinding...", "warn")
        result = run("kubectl create clusterrolebinding kubernetes-admin-binding --clusterrole=cluster-admin --user=kubernetes-admin")
        if "created" in result:
            log("ClusterRoleBinding успешно создан", "ok")
        else:
            log(f"Не удалось создать ClusterRoleBinding: {result}", "error")


if __name__ == "__main__":
    verify_cert_chain()
    ensure_kubeconfig_env()
    ensure_rbac()
    test_kubectl()
