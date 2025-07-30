# Шаблоны и файлы каталога `data`

Каталог `data` содержит набор шаблонов и вспомогательных файлов, которые
используются скриптами из корня проекта. Большинство файлов оформлено как
шаблоны Jinja2 (`*.j2`) и подставляют параметры во время выполнения.
Ниже описано назначение каждой поддиректории и основных файлов.

## `collect_node_info.py`
Скрипт собирает базовые сведения об узле (IP‑адрес, архитектуру,
дистрибутив, роль ноды) и сохраняет их в `collected_info.py`. При запуске с
ключом `-cpb` дополнительно генерирует токен `kubeadm`, вычисляет хеш CA и
подготавливает публичный ключ для подключения воркеров.

## `required_binaries.yaml`
YAML‑файл со списками бинарников, которые должны быть доступны на ноде.
Используется скриптами из `setup/` для проверки и загрузки недостающих
исполняемых файлов.

## `etcd.service.template`
Шаблон systemd‑unit для standalone экземпляра `etcd`. Значения `{IP}` и
`{HOSTNAME}` подставляются скриптами на этапе генерации файла службы.

## `10-kubelet.conf/`
Набор drop‑in файлов для `kubelet` (директория
`/etc/systemd/system/kubelet.service.d/`).
Шаблоны применяются поэтапно:

- `bootstrap-step.conf.j2` – старт kubelet в режиме bootstrap с минимальным
набором аргументов.
- `flags-step.conf.j2` – патч конфигурации на раннем этапе установки.
- `memory-step.conf.j2` – вариант с ограничением памяти через cgroup slice.
- `prod-step.conf.j2` – финальная конфигурация после установки CNI.
- `flags-step.conf.j2.example` – пример содержимого для справки.

## `conf/`
Kubeconfig‑файлы и конфигурация kubelet:

- `admin.conf.j2` – kubeconfig администратора для control‑plane.
- `admin_worker.conf.j2` – kubeconfig для Cilium на воркерах.
- `kubelet.conf.j2` – kubeconfig для kubelet на control‑plane.
- `var_lib_kubelet_config.conf.j2` – основной YAML с параметрами
`KubeletConfiguration`.

## `cni/`
Шаблоны конфигурации Cilium CNI:

- `cilium.conflist.j2` – файл `/etc/cni/net.d/00-cilium.conflist`.
- `cilium_values.yaml.j2` – значения для установки Cilium через Helm.

## `crds/`
Полные манифесты CRD проекта Cilium. Файлы разбиты по версиям API в
подкаталоги `v2/` и `v2alpha1/` и применяются при инициализации кластера.

## `systemd/`
Шаблоны unit‑файлов для различных сервисов Kubernetes и вспомогательных
утилит:

- `apiserver_dev.service.j2` и `apiserver_prod.service.j2` – запуски
`kube-apiserver` в режимах *dev* и *prod*.
- `controller_manager.service.j2` – unit для kube-controller-manager.
- `scheduler.service.j2` – unit kube-scheduler.
- `kubelet.service.j2` и `kubelet.slice.j2` – служба kubelet и выделенный slice.
- `cilium.service.j2` – запуск демона Cilium из systemd.
- `intake_ipam.service.j2` – сервис для встроенного IPAM/Intake клиента.
- `envoy.service` – отдельный unit для Envoy, используемый Cilium.

## `yaml/`
Различные YAML‑манифесты и шаблоны:

- `bootstrap-token.yaml.j2` – шаблон для генерации bootstrap‑токена kubeadm.
- `cilium.yaml.j2` и `cilium-operator-pod.yaml` – конфигурация и под оператора
Cilium.
- `cilium-nodeconfig-cp.yaml` – NodeConfig для control‑plane с маской
подсети.
- `cluster-info-configmap.yaml.j2` – ConfigMap с публичной информацией о
кластере для начальной инициализации.
- `coredns_configmap.yaml` и `coredns_deployment.yaml` – простая настройка
CoreDNS.
- `envoy.yaml.j2` – базовый конфиг Envoy для Cilium.
- `kubeadm-config.yaml.j2` – основная конфигурация `kubeadm init`.
- `kubelet_config_worker.yaml` – конфиг kubelet для worker‑нод.
- поддиректория `rbac/` содержит несколько файлов ClusterRole и
ClusterRoleBinding, используемых для прав доступа API‑server и Cilium.

---
Все файлы из `data/` копируются или рендерятся скриптами в соответствующие
места на узле во время работы `main.py`.
