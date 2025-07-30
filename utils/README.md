# Вспомогательные скрипты Kubernetes Bootstrap

Этот раздел описывает все скрипты из папки `utils/`, `scripts/` и других, которые не входят в основной пайплайн, но могут быть полезны для отладки, очистки или вспомогательной логики.

---

### `logger.py`

* **Описание:** Система логирования для всех питонских скриптов.
* **Функция `log(text, level)`**:

  * `info` — синий
  * `warn` — жёлтый
  * `error` — красный
  * `ok` — зелёный

---

### `rm_cilium_pods.sh`

* **Цель:** Удаление Cilium полностью с ноды.
* **Функции:**

  * `helm uninstall` Cilium
  * Удаление ConfigMap `cilium-config`
  * Удаление CRD и Cilium Pod
  * Чистка BPF-программ и карт
  * `umount` `/sys/fs/bpf` и `/run/cilium/cgroupv2`
  * `systemctl restart containerd && kubelet`
  * Перезагрузка (`reboot`)
* **Логи пишутся в `/opt/kuber-bootstrap/logs/cilium_rm_*.log`**

---

### `collect_cilium_pods_logs.sh`

* **Цель:** Собрать логи всех Cilium Pod'ов в `kube-system` нейспейсе.
* **Выход:** файл `/opt/kuber-bootstrap/logs/cilium_pods_logs_TIMESTAMP.log`

---

### `debug_cilium_agent.py`

* **Цель:** Проверка путей, сокетов, конфигов Cilium, обнаружение ошибок в systemd.
* **Полезен для:** дебага Cilium перед запуском или при `CrashLoop`.

---

### `cleanup_kuber.sh`

* **Цель:** Чистка Kubernetes кластера (конфигов, сертификатов, kubelet, etcd и пр.).
* **Полезно:** для полной сброски кластера и повторной инициализации.

---
