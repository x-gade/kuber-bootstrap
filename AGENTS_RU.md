# AGENTS.md

Этот документ служит внутренним руководством для разработчиков, работающих со скриптами установки.
Название `AGENTS.md` происходит от концепции агентного workflow Codex и не связано с CI/CD-агентами.

Репозиторий содержит скрипты для установки Kubernetes-нод без встроенного etcd.
Все скрипты написаны на чистом Python 3 и используют только стандартную библиотеку и Jinja2.

## Требования

- Python 3.8+
- Jinja2 (`pip install jinja2`)
- Root-права для установки systemd-юнитов и бинарников

## Обзор директорий

- `data/collect_node_info.py` — сбор основных данных о хосте и запись в `data/collected_info.py`.
- `setup/` — установка зависимостей (`install_dependencies.py`), проверка бинарников (`check_binaries.py`), установка Helm (`install_helm.py`).
- `certs/` — генерация сертификатов (`generate_all.py`) и их обновление (`renew_certs.py`).
- `kubeadm/` — генерация конфигурации kubeadm и запуск фаз инициализации.
- `kubelet/` — создание конфигурации и kubeconfig для kubelet, управление параметрами сервиса.
- `systemd/` — создание systemd unit-файлов для etcd и kube-apiserver.
- `post/` — установка CNI, установка меток на ноду и другие пост-действия.
- `cluster/` — скрипты для обслуживания кластера (проверка состояния, генерация конфигов).
- `data/` — шаблоны и список необходимых бинарников, используемые в скриптах.
- `main.py` — оркестратор всей установки.

## Использование

Выполните `python3 main.py control-plane` для установки управляющего узла или `python3 main.py node` для обычной ноды.
Каждый шаг логируется с цветовой маркировкой через `utils/logger.py`. Убедитесь, что `data/collect_node_info.py` уже выполнен и создал `data/collected_info.py`.

## Роли узлов

Скрипт `data/collect_node_info.py` записывает `data/collected_info.py` с информацией о машине, включая её роль (`control-plane` или `node`). `main.py` читает этот файл, чтобы определить порядок выполнения шагов. Запускайте `collect_node_info.py` на каждой машине и сохраняйте полученный файл рядом со скриптами или перенесите его перед запуском `main.py`.

## Обзор этапов установки

### control-plane

1. `data/collect_node_info.py` — сбор информации о хосте
2. `setup/install_dependencies.py` — установка необходимых пакетов
3. `setup/check_binaries.py` — проверка наличия бинарников (kubeadm, etcd и др.)
4. `setup/install_binaries.py` — загрузка отсутствующих бинарников
5. `kubelet/generate_kubelet_conf.py` — генерация конфигурации kubelet
6. `kubelet/manage_kubelet_config.py --mode memory` — настройка лимитов по памяти
7. `kubelet/manage_kubelet_config.py --mode flags` — добавление флагов и перезапуск kubelet
8. `post/enable_temp_network.py` — временная сеть для установки CNI
9. `setup/install_helm.py` — установка Helm
10. `certs/generate_all.py` — генерация TLS-сертификатов
11. `kubelet/generate_kubelet_kubeconfig.py` — создание kubeconfig для kubelet
12. `systemd/generate_etcd_service.py` — генерация и запуск systemd-сервиса etcd
13. `systemd/generate_apiserver_service.py --mode=dev` — запуск kube-apiserver в ослабленном режиме
14. `kubeadm/generate_kubeadm_config.py` — генерация конфигурации для kubeadm
15. `kubeadm/generate_admin_kubeconfig.py` — создание kubeconfig для kubectl
16. `kubeadm/run_kubeadm_phases.py` — выполнение фаз инициализации кластера
17. `post/install_go.py` — установка Go toolchain
18. `post/install_cni_binaries.py` — сборка и установка Cilium
19. `post/apply_cni.py` — применение CNI-манифеста и удаление временной сети
20. `post/label_node.py` — установка меток и taint для управляющей ноды
21. `post/initialize_control_plane_components.py` — запуск controller-manager и scheduler
22. `systemd/generate_apiserver_service.py --mode=prod` — перевод kube-apiserver в безопасный режим

В режиме `--mode=dev` API-сервер позволяет привилегированные операции и отключает PodSecurity. После установки CNI он перезапускается в `--mode=prod` с жёсткими политиками доступа.

### node

1. `data/collect_node_info.py` — сбор информации о хосте
2. `setup/install_dependencies.py` — установка зависимостей
3. `setup/check_binaries.py` — проверка бинарников
4. `setup/install_binaries.py` — загрузка отсутствующих бинарников
5. `kubelet/manage_kubelet_config.py --mode flags` — настройка флагов и перезапуск kubelet
6. `setup/install_helm.py` — установка Helm
7. `post/join_nodes.py` — выполнение команды присоединения к кластеру

## Стандарты кода

- Используйте синтаксис Python 3.8+ и не добавляйте ненужных зависимостей.
- Логирование делайте через `log()` из `utils/logger.py` для единообразия.
- После генерации systemd-юнитов обязательно вызывайте `systemctl daemon-reexec` и `systemctl daemon-reload`.
- Храните все временные и сгенерированные файлы в `data/` или под `/etc/kubernetes`.
- Не коммитьте файлы, указанные в `.gitignore` (например, `certs/cert_info.json`, `data/collected_info.json`).

## Добавление нового скрипта

- Поместите скрипт в соответствующую папку (`setup/`, `certs/`, `kubeadm/` и т.д.).
- Добавьте его вызов в `main.py` в нужной последовательности.
- Используйте `log("[STEP] <описание операции>")`, чтобы стиль логов был единым.

## Валидация

Автоматических тестов нет. Перед коммитом убедитесь, что все скрипты компилируются:

```bash
python -m py_compile $(git ls-files '*.py')
```

Это гарантирует отсутствие синтаксических ошибок.
