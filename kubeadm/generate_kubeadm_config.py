# kubeadm/generate_kubeadm_config.py

import sys
import os
import shutil
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import log
from data import collected_info

OUTPUT_FILE = "data/kubeadm-config.yaml"

def is_kubeadm_available():
    return shutil.which("kubeadm") is not None

def generate_config():
    if not is_kubeadm_available():
        log("kubeadm не найден, пропускаю генерацию конфигурации", "error")
        return

    if collected_info.ROLE != "control-plane":
        log("kubeadm-config.yaml генерируется только на control-plane узле", "warn")
        return

    log("Генерация kubeadm-config.yaml...", "info")

    content = f"""apiVersion: kubeadm.k8s.io/v1beta3
kind: InitConfiguration
localAPIEndpoint:
  advertiseAddress: {collected_info.IP}
  bindPort: 6443
---
apiVersion: kubeadm.k8s.io/v1beta3
kind: ClusterConfiguration
kubernetesVersion: stable
controlPlaneEndpoint: "{collected_info.IP}:6443"
networking:
  podSubnet: "{collected_info.CLUSTER_POD_CIDR}"
etcd:
  external:
    endpoints:
      - https://{collected_info.IP}:2379
    caFile: /etc/kubernetes/pki/etcd/ca.crt
    certFile: /etc/kubernetes/pki/apiserver-etcd-client.crt
    keyFile: /etc/kubernetes/pki/apiserver-etcd-client.key
"""

    with open(OUTPUT_FILE, "w") as f:
        f.write(content)

    log(f"Файл создан: {OUTPUT_FILE}", "ok")

if __name__ == "__main__":
    generate_config()
