# Установка зависимостей для Kubernetes-узлов

Данный набор скриптов отвечает за полную подготовку основных зависимостей, бинарников и утилит для работы Kubernetes-кластера. Они могут быть запущены в качестве части CI/CD пайплайна или ручно при пошаговой инсталляции.

---

## `install_dependencies.py`

**Цель:** Установка основных systemd/библиотечных зависимостей для Kubernetes, включая:

* `containerd`, `conntrack`, `socat`, `iproute2`
* `bpftool` (через `linux-tools`) и его runtime-библиотеки
* `curl`, `ca-certificates`, `gnupg`

**Поток работы:**

1. `apt-get update`
2. Установка пакетов
3. Ссылка `bpftool` в `/usr/local/bin`

---

## `install_binaries.py`

**Цель:** Установка отсутствующих бинарников (например, `kubelet`, `kubeadm`, `kubectl`, `cilium`) из `binares/*.tar.gz`.

**Формат:**

* Входные данные: `missing_binaries.json`
* Целевая директория: `/usr/local/bin`, `/usr/bin` (для `kubelet`)

---

## `check_binaries.py`

**Цель:** Проверка наличия всех необходимых бинарников для кластера.

**Описывает:**

* Каждый бинарник: найден ли в `PATH`
* Создает `missing_binaries.json` для `install_binaries.py`

---

## `install_helm.py`

**Цель:** Установка Helm (пакетный менеджер Kubernetes)

**Поток работы:**

1. Проверка: `helm` уже установлен? Если да — выход
2. Скачивание GPG-ключа и архива
3. Добавление репо и `apt install helm`

---
