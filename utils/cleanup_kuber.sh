#!/usr/bin/env bash
# Безопасная локовая очистка ноды после kubeadm reset.
# Делает: стоп сервисов, рекурсивный umount cgroup/BPF, чистку CNI, iptables/ipvs, kube-файлов.

set -Eeuo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "[INFO] Перезапускаюсь с sudo..."
  exec sudo -E bash "$0" "$@"
fi

log() {
  local lvl="$1"; shift
  case "$lvl" in
    ok)   printf "[OK] %s\n" "$*";;
    warn) printf "[WARN] %s\n" "$*";;
    err)  printf "[ERROR] %s\n" "$*" >&2;;
    *)    printf "[INFO] %s\n" "$*";;
  esac
}

stop_services() {
  # Отключаем и останавливаем связанные сервисы (игнорируем ошибки, если их нет)
  systemctl stop cilium.service 2>/dev/null || true
  systemctl stop cilium-health-responder.service 2>/dev/null || true
  systemctl stop kubelet.service 2>/dev/null || true

  systemctl disable cilium.service 2>/dev/null || true
  systemctl disable cilium-health-responder.service 2>/dev/null || true
  systemctl disable kubelet.service 2>/dev/null || true

  # На всякий случай прибиваем процессы Cilium
  pkill -f 'cilium-agent' 2>/dev/null || true
  pkill -f 'cilium-health' 2>/dev/null || true
}

is_mounted() {
  # usage: is_mounted /path && echo yes
  mountpoint -q "$1"
}

umount_tree() {
  # Рекурсивный umount всех вложенных маунтов под указанным путем
  local root="$1"
  [[ -d "$root" ]] || return 0

  # Список маунтов под root (глубокие — первыми), по данным /proc/self/mountinfo
  # shellcheck disable=SC2013
  while read -r mnt; do
    if is_mounted "$mnt"; then
      umount -f "$mnt" 2>/dev/null || umount "$mnt" 2>/dev/null || umount -l "$mnt" 2>/dev/null || true
    fi
  done < <(awk -v p="$root" '{print $5}' /proc/self/mountinfo | grep -E "^"$(printf "%q" "$root") | awk '{print length, $0}' | sort -nr | cut -d" " -f2)

  # Корневой сам тоже пробуем отмонтировать
  if is_mounted "$root"; then
    umount -f "$root" 2>/dev/null || umount "$root" 2>/dev/null || umount -l "$root" 2>/dev/null || true
  fi
}

cleanup_cilium_mounts() {
  # Часто Cilium монтирует cgroup v2 и bpffs
  if [[ -d /run/cilium/cgroupv2 ]]; then
    log info "Umount Cilium cgroupv2 под /run/cilium/cgroupv2 ..."
    umount_tree /run/cilium/cgroupv2
  fi

  # BPF FS может быть в /sys/fs/bpf или под /run/cilium/bpffs
  for bpfcand in /sys/fs/bpf /run/cilium/bpffs; do
    if [[ -d "$bpfcand" ]]; then
      if is_mounted "$bpfcand"; then
        log info "Umount bpffs $bpfcand ..."
        umount -f "$bpfcand" 2>/dev/null || umount "$bpfcand" 2>/dev/null || umount -l "$bpfcand" 2>/dev/null || true
      fi
    fi
  done
}

cleanup_cni() {
  # kubeadm reset это не чистит — делаем сами
  rm -rf /etc/cni/net.d 2>/dev/null || true
  rm -rf /var/lib/cni 2>/dev/null || true
  rm -rf /var/run/cni 2>/dev/null || true
}

flush_net_rules() {
  # iptables/ip6tables могут отсутствовать — игнорируем ошибки
  command -v iptables >/dev/null 2>&1 && { iptables -F || true; iptables -t nat -F || true; iptables -t mangle -F || true; }
  command -v ip6tables >/dev/null 2>&1 && { ip6tables -F || true; ip6tables -t nat -F || true; ip6tables -t mangle -F || true; }
  # IPVS если включался
  command -v ipvsadm >/dev/null 2>&1 && { ipvsadm -C || true; }
}

cleanup_fs() {
  # После umount удаляем каталоги
  rm -rf /run/cilium 2>/dev/null || true
  rm -rf /var/run/cilium 2>/dev/null || true
  rm -rf /var/lib/cilium 2>/dev/null || true
  rm -rf /etc/cilium 2>/dev/null || true

  # kube-хвосты (часть уже удалил kubeadm reset)
  rm -rf /etc/kubernetes 2>/dev/null || true
  rm -rf /var/lib/kubelet 2>/dev/null || true
  rm -rf /var/lib/etcd 2>/dev/null || true

  # .kube пользователя root/текущего юзера
  rm -rf /root/.kube 2>/dev/null || true
  if [[ -n "${SUDO_USER:-}" ]]; then
    rm -rf "/home/${SUDO_USER}/.kube" 2>/dev/null || true
  fi
}

main() {
  log info "Останавливаю сервисы (cilium/kubelet)..."
  stop_services
  log ok "Сервисы остановлены"

  log info "Umount Cilium cgroup/BPF маунтов..."
  cleanup_cilium_mounts
  log ok "Маунты отмонтированы"

  log info "Чищу CNI каталоги..."
  cleanup_cni

  log info "Сбрасываю iptables/ip6tables/ipvs (если доступны)..."
  flush_net_rules

  log info "Чищу файловую систему от хвостов..."
  cleanup_fs

  log ok "Локовая очистка завершена."
}

main "$@"