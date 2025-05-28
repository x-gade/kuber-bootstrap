# cluster/generate_cluster_config.py

import os
import json
from data.collected_info import IP, CLUSTER_POD_CIDR
from utils.logger import log

CONFIG_PATH = "data/cluster_config.json"
DEFAULT_SERVICE_CIDR = "10.96.0.0/12"

def generate(service_cidr=DEFAULT_SERVICE_CIDR):
    config = {
        "cluster_name": "uniaff",
        "pod_cidr": CLUSTER_POD_CIDR,
        "service_cidr": service_cidr,
        "control_planes": [IP]
    }

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                existing = json.load(f)
            if IP not in existing.get("control_planes", []):
                existing["control_planes"].append(IP)
            existing["control_planes"] = sorted(set(existing["control_planes"]))
            config = existing
            log("cluster_config.json дополнён", "info")
        except Exception as e:
            log(f"Ошибка чтения cluster_config.json: {e}", "error")
            return

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    log(f"Конфигурация кластера сохранена: {CONFIG_PATH}", "ok")

if __name__ == "__main__":
    generate()
