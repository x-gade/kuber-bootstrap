# Kuber Bootstrap

<<<<<<< HEAD
Инструмент для ручного развёртывания узлов Kubernetes без встроенного etcd. Скрипты написаны на Python 3 и используют только стандартную библиотеку и Jinja2.

## Требования

- Python 3.8+
- Jinja2 (`pip install jinja2`)
- root-права для создания systemd unit'ов и сертификатов

## Состав репозитория

- `data/collect_node_info.py` – собирает IP, архитектуру и роль узла, сохраняет в `data/collected_info.py`.
- `setup/` – установка зависимостей и Helm, проверка бинарников.
- `certs/` – генерация и проверка сертификатов.
- `kubeadm/` – подготовка конфигурации и запуск фаз инициализации.
- `kubelet/` – создание конфигурации kubelet и kubeconfig.
- `systemd/` – генерация unit-файлов для etcd и kube-apiserver.
- `post/` – установка CNI и постконфигурация control-plane.
- `cluster/` – вспомогательные утилиты для проверки состояния кластера.
- `data/` – шаблоны unit-файлов и прочие параметры.
- `main.py` – оркестратор, выполняющий шаги установки.

## Быстрый старт

1. Запустите `python3 main.py control-plane` для control-plane либо `python3 main.py node` для worker-ноды.
2. Скрипт поочерёдно выполнит все необходимые шаги, выводя ход процесса в консоль.

## Этапы установки

### Control-plane

1. Установка зависимостей и проверка бинарников.
2. Настройка kubelet и временной сети.
3. Генерация всех сертификатов.
4. Запуск etcd и kube-apiserver в режиме *dev*.
5. Генерация конфигурации kubeadm и kubeconfig'ов.
6. Инициализация кластера и установка Cilium.
7. Запуск controller-manager и scheduler, перевод apiserver в режим *prod*.

### Worker

1. Установка зависимостей и проверка бинарников.
2. Патч параметров kubelet и установка Helm.
3. Выполнение команды `kubeadm join` (скрипт ожидается в будущем).

## Проверка кода

Автотесты отсутствуют. Для проверки синтаксиса выполните:

```bash
python -m py_compile $(git ls-files '*.py')
```
=======
Инструмент для ручного и полуавтоматического развёртывания узлов Kubernetes на Ubuntu 22.04 с выносом control‑plane компонентов в systemd. Скрипты написаны на Python 3 и Bash. Используются стандартная библиотека Python, Jinja2 и минимальный набор сторонних пакетов.

## Требования

* Ubuntu 22.04 (root или sudo)
* Python 3.8+
* Bash
* Доступ в интернет для установки системных и Python‑зависимостей

## Быстрый старт

### Установка/запуск узла через `install.sh`

```bash
# Сделать исполняемым и запустить
chmod +x /opt/kuber-bootstrap/install.sh

# Worker-узел
/opt/kuber-bootstrap/install.sh -w

# Control-plane узел
/opt/kuber-bootstrap/install.sh -cp

# Control-plane bootstrap (инициализация CP)
/opt/kuber-bootstrap/install.sh -cpb
```

`install.sh` перед любым из режимов делает:

1. `apt-get update` и установку пакетов: `python3-argcomplete`, `python3-venv`, `python3-pip`.
2. Создаёт/обновляет виртуальное окружение в `/opt/kuber-bootstrap/.venv`.
3. Обновляет `pip/setuptools/wheel` и устанавливает зависимости из `requirements.txt`:

   * `fastapi==0.110.0`
   * `uvicorn[standard]==0.29.0`
   * `jinja2==3.1.4`
   * `pyjwt==2.9.0`
   * а также гарантирует наличие `argcomplete` внутри venv.
4. Запускает `python main.py` в соответствующем режиме.

### Удаление узла через `uninstall.sh`

```bash
# Сделать исполняемым и запустить
chmod +x /opt/kuber-bootstrap/uninstall.sh

# Удаление worker-узла
/opt/kuber-bootstrap/uninstall.sh -wd

# Удаление control-plane узла
/opt/kuber-bootstrap/uninstall.sh -cpd
```

`uninstall.sh`:

1. Выбирает Python интерпретатор: предпочитает venv (`.venv/bin/python`), иначе системный `python3`.
2. Запускает `cluster/intake_services/init_services.py` с нужным флагом:

   * `-wd` — удаление worker-ноды из кластера (предварительно опрашивает актуальный join‑токен/права).
   * `-cpd` — удаление control‑plane узла (аналогично опрашивает токен/права).
3. Независимо от результата шага 2 запускает локовую очистку: `utils/cleanup_kuber.sh`.

Коды выхода: `0` — успех; `10/11` — ошибки инициализации удаления (для `-wd` / `-cpd`); `20` — ошибка локовой очистки.

## Режимы скриптов

### `install.sh`

* `-w`  — устанавливает зависимости и запускает `python main.py worker`.
* `-cp` — устанавливает зависимости и запускает `python main.py control-plane`.
* `-cpb` — устанавливает зависимости и запускает bootstrap control‑plane: `python main.py control-plane --bootstrap` (если флаг не поддерживается — пробует позиционный аргумент `bootstrap`).

Переменные окружения:

* `DEBIAN_FRONTEND=noninteractive` — управление поведением APT.

### `uninstall.sh`

* `-wd`  — кластерное удаление worker-ноды (`init_services.py -wd`), затем локовая очистка (`cleanup_kuber.sh`).
* `-cpd` — кластерное удаление control‑plane узла (`init_services.py -cpd`), затем локовая очистка.

Переменные окружения:

* `PYTHON_BIN=/path/to/python` — принудительный выбор интерпретатора Python.
* `FORCE_CLEANUP=1` — запуск локовой очистки даже если шаг удаления завершился ошибкой (по умолчанию и так выполняется всегда).

## Состав репозитория

* `install.sh` — унифицированный инсталлятор режимов worker/control‑plane/CP bootstrap с подготовкой APT и Python‑окружения.
* `uninstall.sh` — деинсталлятор worker/control‑plane с кластерным удалением и локовой очисткой.
* `main.py` — оркестратор шагов установки.
* `data/collect_node_info.py` — сбор IP, hostname, роли узла; сохраняет в `data/collected_info.py`.
* `setup/` — установка системных зависимостей и бинарников, проверка и докачка недостающих.
* `systemd/` — генерация unit‑файлов для `kube-apiserver`, `controller-manager`, `scheduler`, `cilium-agent` и др.
* `certs/` — генерация/ротация сертификатов, таймеры обновления.
* `kubeadm/` — подготовка конфигураций и фаз инициализации.
* `kubelet/` — генерация конфигурации и kubeconfig для kubelet.
* `post/` — установка CNI, post‑конфигурация CP/worker.
* `cluster/` — IPAM/patcher CiliumNode, intake‑сервисы, вспомогательные утилиты.
* `utils/` — вспомогательные скрипты, в т.ч. `cleanup_kuber.sh`.

## Этапы установки (общее представление)

### Control‑plane

1. Установка системных зависимостей и проверка/доставка бинарников.
2. Настройка kubelet и временной сети.
3. Генерация сертификатов и kubeconfig.
4. Запуск `etcd` и `kube-apiserver` (dev‑режим на этапе bootstrap, далее prod‑флаги).
5. Инициализация кластера, установка Cilium.
6. Запуск `controller-manager` и `scheduler` под systemd.

### Worker

1. Установка системных зависимостей и бинарников.
2. Подготовка `containerd`, kubelet и конфигов.
3. Присоединение в кластер (join) и сетевые патчи (в т.ч. CiliumNode IPAM‑патчинг).

## Примеры

```bash
# Worker установка
/opt/kuber-bootstrap/install.sh -w

# Control‑plane bootstrap
/opt/kuber-bootstrap/install.sh -cpb

# Удаление worker-ноды
/opt/kuber-bootstrap/uninstall.sh -wd
```

## Проверка кода

```bash
python -m py_compile $(git ls-files '*.py')
```

## Краткие описания скриптов

* `install.sh` — единая точка входа для установки: готовит APT‑пакеты, создаёт venv, ставит Python‑зависимости и запускает `main.py` в нужном режиме (`-w`, `-cp`, `-cpb`). Идемпотентен и безопасен к повторным запускам.
* `uninstall.sh` — единая точка выхода: инициирует кластерное удаление узла через `cluster/intake_services/init_services.py` (`-wd`/`-cpd`) и затем выполняет локовую очистку через `utils/cleanup_kuber.sh`. Возвращает информативные коды ошибок.
>>>>>>> origin/test
