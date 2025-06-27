#!/bin/bash

timestamp=$(date '+%Y%m%d_%H%M%S')
output_dir="logs/cilium_diagnostics_$timestamp"
mkdir -p "$output_dir"

echo "[INFO] Сохраняем диагностику Cilium в: $output_dir"

# ─── Статус всех pod'ов cilium ────────────────────────────────────────────────
kubectl get pods -n kube-system -o wide | grep -i cilium > "$output_dir/pods_status.txt" || echo "[WARN] Cilium-поды не найдены"

# ─── Логи и describe для всех pod'ов с именем, содержащим cilium ──────────────
kubectl get pods -n kube-system -o name | grep -i cilium | while read -r pod; do
    name=$(basename "$pod")
    echo "[INFO] Сохраняем логи и описание $name"
    kubectl logs -n kube-system "$name" > "$output_dir/logs_${name}.log" 2>&1
    kubectl describe pod -n kube-system "$name" > "$output_dir/describe_${name}.txt" 2>&1
done

# ─── Статус и describe нод ─────────────────────────────────────────────────────
kubectl get nodes -o wide > "$output_dir/nodes_status.txt"

kubectl get nodes --no-headers | awk '{print $1}' | while read -r node; do
    kubectl describe node "$node" > "$output_dir/describe_node_${node}.txt" 2>&1
done

# ─── События ───────────────────────────────────────────────────────────────────
kubectl get events -n kube-system --sort-by='.lastTimestamp' > "$output_dir/kube_system_events.txt"

echo "[OK] Диагностика завершена. Всё сохранено в: $output_dir"
