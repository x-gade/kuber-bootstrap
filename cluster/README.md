# IPAM — CIDR для Kubernetes-нод: `mapper.py` и `patcher.py`

## Общее описание

Эти скрипты являются частью IPAM-системы для Kubernetes-кластера с поддержкой Cilium. Они отвечают за:

* раздачу CIDR-блоков для control-plane и worker-нод
* удаление CIDR при деделе
* патч объектов Node/СiliumNode

---

## `mapper.py`

### Роль

* Автоматически выдает CIDR-блоки из пределов:

  * `/26` для control-plane (10.244.0.0/24)
  * `/24` для worker (10.244.0.0/16)
* Запись карт в:

  * `data/control_plane_map.json`
  * `data/worker_map.json`

### Ключевые флаги

* `--action register|delete`
* `--name` — имя ноды
* `--ip` — её IP
* `--role` — control-plane | worker
* `--cpb` — взять данные из collected\_info

### Выход (JSON)

```json
{
  "role": "worker",
  "name": "worker-node-1",
  "globalip": "192.168.1.10",
  "cidr": "10.244.12.0/24"
}
```

---

## `patcher.py`

### Роль

* Найти объект Node в Kubernetes
* Скоррелировать его с записью в карте CIDR
* Патчить объект CiliumNode:

  * `spec.ipam.podCIDRs`
  * `spec.ipam.routes`

### Ключевой вызов

```bash
python3 patcher.py --cpb
```

(данные берутся из `collected_info.py`)

---

## Связь в пайплайне

1. `worker_bootstrap.py`

   * Запись роли/имени/IP в collected\_info
2. `mapper.py`

   * Привязка CIDR к ноде
3. `patcher.py`

   * Патч CiliumNode

---

## Зависимости

* `data/collected_info.py`
* `data/control_plane_map.json`, `worker_map.json`
* Kubernetes API
* Cilium CustomResourceDefinitions

---

## Пример

```bash
python3 mapper.py --action register --cpb
python3 patcher.py --cpb
```

---

Эти скрипты обеспечивают ролевое IP-дерево для сети Cilium и детерминируемую раздачу подсетей по ролям нод.
