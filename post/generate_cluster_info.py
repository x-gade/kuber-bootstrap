"""
Generate and apply the cluster-info ConfigMap for kubeadm bootstrap.

Генерация и применение ConfigMap cluster-info для подключения новых нод через kubeadm.
"""

import os
import sys
from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log

# Пути
TEMPLATE_DIR = "data/yaml"
TEMPLATE_FILE = "cluster-info-configmap.yaml.j2"
OUTPUT_PATH = "/tmp/cluster-info-configmap.yaml"

# Загрузка информации
try:
    import data.collected_info as info
except Exception as e:
    log(f"Не удалось загрузить collected_info.py: {e}", "error")
    raise SystemExit(1)

# Проверка полей
required_fields = ["IP", "JOIN_TOKEN", "CA_CERT_BASE64"]
for field in required_fields:
    if not hasattr(info, field):
        log(f"Отсутствует поле {field} в collected_info.py", "error")
        raise SystemExit(1)

# Рендеринг шаблона
try:
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template(TEMPLATE_FILE)
    rendered = template.render(
        PUBLIC_IP=info.IP,
        TOKEN=info.JOIN_TOKEN,
        CA_BASE64=info.CA_CERT_BASE64
    )

    with open(OUTPUT_PATH, "w") as f:
        f.write(rendered)

    log("Файл cluster-info-configmap.yaml успешно сгенерирован", "ok")
except Exception as e:
    log(f"Ошибка генерации шаблона: {e}", "error")
    raise SystemExit(1)

# Применение через kubectl
try:
    result = os.system(f"kubectl apply -f {OUTPUT_PATH}")
    if result == 0:
        log("ConfigMap 'cluster-info' успешно применён", "ok")
    else:
        log("Ошибка применения ConfigMap через kubectl", "error")
except Exception as e:
    log(f"Сбой при вызове kubectl: {e}", "error")
    raise SystemExit(1)
