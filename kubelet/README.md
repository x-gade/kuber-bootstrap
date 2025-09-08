# Установка и настройка kubelet через шаблоны

Этот набор скриптов обеспечивает полную генерацию конфигураций и запуск `kubelet` согласно единому пайплайну.

## Скрипты

### 1. `generate_kubelet_kubeconfig.py`

Генерирует kubeconfig `/etc/kubernetes/kubelet.conf` из Jinja2-шаблона `data/conf/kubelet.conf.j2`. Если файл уже есть и не изменился по SHA256-хешу, генерация пропускается.

**Вход:**

* `collected_info.IP` — IP адрес ноды
* `data/conf/kubelet.conf.j2` — шаблон

**Выход:**

* `/etc/kubernetes/kubelet.conf` — kubeconfig

### 2. `manage_kubelet_config.py`

Скрипт генерирует `10-kubeadm.conf` — systemd override для `kubelet`, основываясь на Jinja2-шаблонах из `data/10-kubelet.conf/`.

**Режимы:**

* `--mode memory` — лимиты памяти, без перезапуска
* `--mode bootstrap` — урезанный конфиг для старта kubelet
* `--mode flags` — финальный конфиг с `--node-ip` и `--pod-cidr`

**Вход:**

* `collected_info.IP`, `collected_info.CLUSTER_POD_CIDR`, `collected_info.CIDR`
* `data/10-kubelet.conf/*.j2` — шаблоны

**Выход:**

* `/etc/systemd/system/kubelet.service.d/10-kubeadm.conf` — override-файл

**Флаг `--mode` обязателен.** При `memory` перезапуск `kubelet` не требуется, при других режимах — выполняется `daemon-reload`, `restart`, `enable`.

---

Эти скрипты являются частью компонента `/opt/kuber-bootstrap` и полностью интегрированы в пайплайн установки control-plane и worker-нод.
