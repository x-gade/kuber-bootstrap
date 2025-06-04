#!/bin/bash

set -e

echo "[CLEANUP] Остановка systemd-сервисов..."
systemctl stop kubelet || true
systemctl stop etcd || true
systemctl stop kube-apiserver || true
systemctl stop kube-cert-renew.timer || true
systemctl stop kube-cert-renew.service || true

echo "[CLEANUP] Отключение сервисов из автозагрузки..."
systemctl disable kubelet || true
systemctl disable etcd || true
systemctl disable kube-apiserver || true
systemctl disable kube-cert-renew.timer || true
systemctl disable kube-cert-renew.service || true

echo "[CLEANUP] Удаление systemd unit-файлов..."
rm -f /etc/systemd/system/kubelet.service
rm -f /etc/systemd/system/etcd.service
rm -f /etc/systemd/system/kube-apiserver.service
rm -f /etc/systemd/system/kube-cert-renew.service
rm -f /etc/systemd/system/kube-cert-renew.timer
rm -rf /etc/systemd/system/kubelet.service.d
systemctl daemon-reexec
systemctl daemon-reload

echo "[CLEANUP] Удаление бинарников Kubernetes..."
rm -f /usr/local/bin/kubeadm
rm -f /usr/local/bin/kubectl
rm -f /usr/local/bin/kubelet
rm -f /usr/local/bin/kube-apiserver
rm -f /usr/local/bin/etcd

echo "[CLEANUP] Принудительное размонтирование всех залипших kubelet-монтов..."
mount | grep '/var/lib/kubelet' | awk '{print $3}' | xargs -r -n1 umount -l

echo "[CLEANUP] Удаление CNI и runtime конфигураций..."
rm -rf /etc/cni
rm -rf /opt/cni
rm -rf /var/lib/cni
rm -rf /var/lib/kubelet
rm -rf /etc/kubernetes
rm -rf /var/lib/etcd

echo "[CLEANUP] Удаление конфигов и логов..."
rm -rf ~/.kube
rm -rf /root/.kube
rm -f /opt/kuber-bootstrap/collected_info.json
rm -f /opt/kuber-bootstrap/certs/cert_info.json

echo "[CLEANUP] Очистка iptables (можно закомментировать при необходимости)..."
iptables -F || true
iptables -t nat -F || true
iptables -t mangle -F || true
iptables -X || true

echo "[CLEANUP] Kubernetes полностью удалён с машины."
