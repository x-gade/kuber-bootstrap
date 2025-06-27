#!/bin/bash

# ─── Подготовка ───────────────────────────────────────────────────────────────
timestamp=$(date '+%Y%m%d_%H%M%S')
log_file="/opt/kuber-bootstrap/logs/cilium_rm_${timestamp}.log"
exec > >(tee -a "$log_file") 2>&1

echo "===== Начало удаления Cilium [$(date)] ====="
echo "Лог сохраняется в: $log_file"

# ─── Удаление Helm-релиза ─────────────────────────────────────────────────────
echo "Удаляем Cilium через Helm..."
helm uninstall cilium -n kube-system 2>/dev/null || echo "Cilium уже удалён или отсутствует"

# ─── Удаление ConfigMap ───────────────────────────────────────────────────────
echo "Удаляем ConfigMap cilium-config..."
kubectl delete configmap cilium-config -n kube-system --ignore-not-found

# ─── Удаление CRD ─────────────────────────────────────────────────────────────
echo "Удаляем CRD Cilium..."
kubectl get crds | grep cilium | awk '{print $1}' | xargs -r kubectl delete crd

# ─── Удаление зависших подов ──────────────────────────────────────────────────
echo "Удаляем зависшие поды Cilium (если есть)..."
kubectl get pods -n kube-system | grep cilium | awk '{print $1}' | while read pod; do
  echo "Удаляю под $pod"
  kubectl delete pod "$pod" -n kube-system --grace-period=0 --force
done

# ─── Удаление BPF-программ ────────────────────────────────────────────────────
echo "Удаляем BPF-программы Cilium..."
for id in $(bpftool prog show | grep -B 2 cilium | grep 'id' | awk '{print $2}'); do
  echo "Удаляю BPF-программу ID $id"
  bpftool prog detach id "$id" 2>/dev/null || echo "Не удалось отсоединить программу $id (возможно, уже удалена)"
done

# ─── Удаление BPF-карт ────────────────────────────────────────────────────────
echo "Удаляем BPF-карты Cilium..."
for id in $(bpftool map show | grep cilium | awk '{print $1}' | sed 's/://g'); do
  echo "Удаляю BPF-карту ID $id"
  bpftool map delete id "$id" >/dev/null 2>&1 || echo "Не удалось удалить карту $id (возможно, уже очищена)"
done

# ─── Отмонтирование ───────────────────────────────────────────────────────────
echo "Отмонтируем /sys/fs/bpf и /run/cilium/cgroupv2..."
umount /sys/fs/bpf 2>/dev/null || echo "/sys/fs/bpf не был примонтирован или уже размонтирован"
umount /run/cilium/cgroupv2 2>/dev/null || echo "/run/cilium/cgroupv2 не был примонтирован или уже размонтирован"

# ─── Удаление файлов ──────────────────────────────────────────────────────────
echo "Удаляем остаточные файлы..."
rm -rf /sys/fs/bpf/* /run/cilium/cgroupv2/* /etc/cni/net.d/* /opt/cni/bin/cilium-cni 2>/dev/null || echo "Некоторые файлы уже отсутствуют"

# ─── Перезапуск демонов ───────────────────────────────────────────────────────
echo "Перезапускаем containerd и kubelet..."
systemctl restart containerd 2>/dev/null || echo "Не удалось перезапустить containerd (возможно, не установлен)"
systemctl restart kubelet 2>/dev/null || echo "Не удалось перезапустить kubelet (возможно, не установлен)"

# ─── Перезагрузка ─────────────────────────────────────────────────────────────
echo "Удаление завершено. Перезагрузка системы..."
echo "===== Завершение [$(date)] ====="
reboot
