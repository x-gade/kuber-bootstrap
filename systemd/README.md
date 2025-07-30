# systemd-сервисы Kubernetes компонентов

Этот набор Python-скриптов отвечает за генерацию, установку и запуск systemd unit-файлов для компонентов Kubernetes control-plane и Cilium. Каждый скрипт выполняет следующую цепочку:

1. Получение параметров из `collected_info.json` и/или `required_binaries.yaml`.
2. Рендер systemd-шаблона Jinja2.
3. Запись unit-файла в `/etc/systemd/system/`.
4. Перезагрузка systemd, запуск и enable.

---

## Скрипты и их назначение

### `generate_apiserver_service.py`

* Генерирует systemd unit-файл `kube-apiserver.service`.
* Поддерживает 2 режима: `dev` (с ослабленными политиками) и `prod` (production).
* Сконфигурирован для работы вне pod'ов.

### `generate_etcd_service.py`

* Генерирует systemd unit-файл `etcd.service`.
* Учитывает IP-адрес, hostname и конфигурацию cluster-state.

### `generate_controller_manager_service.py`

* Генерирует systemd unit-файл `kube-controller-manager.service`.
* Проверяет, есть ли kubeconfig. Если нет, генерирует через `kubeadm`.

### `generate_scheduler_service.py`

* То же самое для `kube-scheduler.service`.
* Скачивает бинарник при необходимости.

### `generate_kubelet_service.py`

* Генерирует systemd unit `kubelet.service` с опциями без `--register-node`, для bootstrap-режима.

### `generate_kubelet_slice.py`

* Генерирует unit `kubelet.slice` для ограничения ресурсов.
* Активирует и проверяет статус.

### `generate_cilium_service.py`

* Генерирует `cilium.service` для `cilium-agent`, вычитывает IP и nodeName из collected\_info.
* Опционально создаёт `/etc/cilium/cilium.yaml`.

### `generate_envoy_service.py`

* Распаковывает архив `envoy.tar.gz`.
* Устанавливает `cilium-envoy` и генерирует unit `envoy.service`.

---

## Общие режимы запуска

Каждый скрипт запускается отдельно:

```bash
python3 systemd/generate_etcd_service.py
```

Все логи выводятся через `utils/logger.py` цветной консолью.

---

Перед запуском любого скрипта:

* убедитесь, что есть `collected_info.json` и `required_binaries.yaml`
* пути к Jinja2-шаблонам проверены
* бинарники Kubernetes на месте
