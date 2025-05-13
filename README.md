
# ⚙️ Kuber Bootstrap

Инфраструктурный инструмент автоматизации установки Kubernetes control-plane и worker узлов **без использования embedded etcd**, с полной генерацией сертификатов, systemd-юнитов и контрольной логикой через `main.py`.

## 📁 Структура проекта

```
/kuber-bootstrap
│
├── cluster/                            # Скрипты управления состоянием кластера
│   ├── sync_cluster_state.py           # Сканирование, пинг и учёт активных узлов
│   ├── rotate_cluster_certs.py         # Ротация всех сертификатов во всех нодах
│   └── force_cluster_restart.py        # Ручной безопасный перезапуск ключевых компонентов
│
├── setup/
│   ├── install_dependencies.py         # Установка всех нужных пакетов
│   ├── check_binaries.py               # Проверка наличия etcd, kubeadm и пр.
│   └── install_binaries.py             # Скачивание бинарников при отсутствии
│
├── certs/
│   ├── generate_all.py                 # Генерация всех сертификатов с логами
│   ├── renew_certs.py                  # Проверка и обновление устаревших сертификатов
│   └── cert_info.json                  # Файл метаданных (не добавляется в git)
│
├── systemd/
│   ├── generate_etcd_service.py        # Юнит и автозапуск etcd
│   └── generate_apiserver_service.py   # (опционально) запуск kube-apiserver как systemd unit
│
├── kubeadm/
│   ├── create_certificates.py          # Генерация TLS для kubeadm
│   ├── generate_kubeadm_config.py      # Генерация kubeadm-config.yaml
│   └── run_kubeadm_init.py             # Запуск kubeadm init без etcd
│
├── post/
│   ├── apply_cni.py                    # Применение сетевого плагина (Flannel/Cilium)
│   ├── patch_controller_flags.py       # Дополнительные флаги для controller-manager/scheduler
│   └── join_nodes.py                   # Генерация `kubeadm join` или join-config.yaml
│
├── utils/
│   ├── logger.py                       # Цветной логгер
│   ├── shell.py                        # Обёртка для subprocess
│   ├── cert_helpers.py                 # Проверка/валидность сертификатов
│   └── validator.py                    # Проверка выполненных шагов
│
├── data/
│   ├── required_binaries.yaml          # Что обязательно должно быть установлено
│   ├── missing_binaries.json           # Что нужно установить (генерируется)
│   └── collected_info.json             # Информация о машине (генерируется)
│
├── logs/
│   └── bootstrap.log                   # Главный лог всех шагов
│
├── collect_node_info.py                # Сбор IP, CIDR, платформы и роли узла
└── main.py                             # Главный оркестратор (в разработке)
```

## 🚀 Поток выполнения

1. `collect_node_info.py` — Сбор системной информации: IP, CIDR, роль, архитектура, ОС.
2. `check_binaries.py` — Проверка нужных бинарников: kubeadm, etcd, containerd и др.
3. `install_dependencies.py` — Установка недостающих компонентов.
4. `generate_all.py` — Генерация CA и сертификатов etcd, API, proxy.
5. `generate_etcd_service.py` — Генерация systemd unit и запуск etcd.
6. `generate_kubeadm_config.py` — Генерация конфигурации kubeadm.
7. `run_kubeadm_init.py` — Инициализация Kubernetes без embedded etcd.
8. `generate_apiserver_service.py` — (опц.) Запуск apiserver как systemd unit.
9. `apply_cni.py` — Установка CNI (по умолчанию Flannel или Cilium).
10. `patch_controller_flags.py` — Добавление нужных флагов в kube-controller.
11. `join_nodes.py` — Подключение worker-ноды.
12. `renew_certs.py` — Плановое обновление сертификатов.
13. `sync_cluster_state.py` — Учёт и регистрация узлов в системе.
14. `rotate_cluster_certs.py` — Централизованная ротация certs (WIP).

## ⚙️ .gitignore (обязательно)

Не добавлять в репозиторий:
- `certs/cert_info.json`
- `data/collected_info.json`
- `data/missing_binaries.json`
- `__pycache__/`
- `logs/`

## 📦 Пример запуска

```bash
python3 collect_node_info.py control-plane
python3 setup/check_binaries.py
python3 setup/install_dependencies.py
python3 certs/generate_all.py
python3 systemd/generate_etcd_service.py
python3 kubeadm/generate_kubeadm_config.py
python3 kubeadm/run_kubeadm_init.py
```

Или в будущем:
```bash
python3 main.py --role control-plane
```

## 🔒 Безопасность

- Все ключи генерируются с `2048` или `4096` бит.
- Используется `openssl` (возможно в будущем cfssl).
- Ведётся журнал всех операций (`logs/bootstrap.log`).

## 📍 Планы:
- [ ] Полная поддержка worker-нод.
- [ ] Интерактивный `main.py` с resume-флагами.
- [ ] Поддержка удалённого деплоя (через ssh).
- [ ] Helm-чарты для модульной установки компонентов.

---

Разработано с ❤️ для инфраструктуры, которая **заслуживает автоматизации**.
