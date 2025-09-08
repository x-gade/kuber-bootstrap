# AGENTS.md

This document serves as an internal developer guide for the bootstrap scripts.
The name `AGENTS.md` comes from the Codex agent workflow and is not related to
CI/CD "agents".

This repository contains scripts for bootstrapping Kubernetes nodes without
embedded etcd. All scripts are plain Python 3 and rely only on the standard
library and Jinja2.

## Requirements

- Python 3.8+
- Jinja2 (`pip install jinja2`)
- Root privileges for installing systemd units and binaries

## Directory overview

- `data/collect_node_info.py` – gather basic host data and write `data/collected_info.py`.
- `setup/` – install dependencies (`install_dependencies.py`), check required binaries (`check_binaries.py`), and install Helm (`install_helm.py`).
- `certs/` – generate certificates (`generate_all.py`) and renew them (`renew_certs.py`).
- `kubeadm/` – generate kubeadm configuration and run kubeadm phases.
- `kubelet/` – create kubelet config and kubeconfig, manage service parameters.
- `systemd/` – create systemd unit files for etcd and kube-apiserver.
- `post/` – apply CNI, label the node and other post-install tasks.
- `cluster/` – scripts for cluster maintenance (health checks, config generation).
- `data/` – templates and required binary lists used by the scripts.
- `main.py` – orchestrates the whole installation pipeline.

## Usage

Run `python3 main.py control-plane` to bootstrap a control plane node or `python3 main.py node` for a worker. Each step prints colored logs via `utils/logger.py`. 
Ensure `data/collect_node_info.py` has been executed so that `data/collected_info.py` exists before running other scripts.

## Node roles

`data/collect_node_info.py` writes `data/collected_info.py` with details about the
machine, including its role (`control-plane` or `node`). `main.py` reads this
file to decide which sequence of steps to execute. Run `data/collect_node_info.py`
on each host and keep the generated file alongside the scripts or transfer it to
another machine before running `main.py`.

## Pipeline steps overview

The exact steps executed by `main.py` differ for a control plane and a worker node.

### control-plane

1. **data/collect_node_info.py** – gather host data
2. **setup/install_dependencies.py** – install required packages
3. **setup/check_binaries.py** – verify presence of kubeadm, etcd and others
4. **setup/install_binaries.py** – download missing binaries (if any)
5. **kubelet/generate_kubelet_conf.py** – create kubelet configuration file
6. **kubelet/manage_kubelet_config.py --mode memory** – write memory limits
7. **kubelet/manage_kubelet_config.py --mode flags** – add kubelet flags and restart
8. **post/enable_temp_network.py** – temporary bridge network used while installing CNI
9. **setup/install_helm.py** – install Helm
10. **certs/generate_all.py** – generate all TLS certificates
11. **kubelet/generate_kubelet_kubeconfig.py** – create kubelet kubeconfig
12. **systemd/generate_etcd_service.py** – generate etcd unit and start service
13. **systemd/generate_apiserver_service.py --mode=dev** – run kube-apiserver with relaxed settings
14. **kubeadm/generate_kubeadm_config.py** – create kubeadm config
15. **kubeadm/generate_admin_kubeconfig.py** – admin kubeconfig for kubectl
16. **kubeadm/run_kubeadm_phases.py** – initialize cluster phases
17. **post/install_go.py** – install Go toolchain
18. **post/install_cni_binaries.py** – build and install Cilium binaries
19. **post/apply_cni.py** – apply CNI manifest and remove temporary bridge
20. **post/label_node.py** – label and taint node as control-plane
21. **post/initialize_control_plane_components.py** – start controller-manager and scheduler
22. **systemd/generate_apiserver_service.py --mode=prod** – switch kube-apiserver to secure mode

While in `--mode=dev` the API server allows privileged operations and disables PodSecurity. After CNI installation it is restarted in `--mode=prod` with stricter admission plugins.

### node

1. **data/collect_node_info.py** – gather host data
2. **setup/install_dependencies.py** – install required packages
3. **setup/check_binaries.py** – verify binaries
4. **setup/install_binaries.py** – download missing binaries
5. **kubelet/manage_kubelet_config.py --mode flags** – add kubelet flags and restart
6. **setup/install_helm.py** – install Helm
7. **post/join_nodes.py** – run the join command produced by the control plane

## Coding conventions

- Use Python 3.8+ syntax and keep scripts free from unnecessary dependencies.
- Logging should use `log()` from `utils/logger.py` to keep message styles consistent.
- Systemd unit generators must reload systemd using `systemctl daemon-reexec` and `systemctl daemon-reload` after writing unit files.
- Keep generated or state files inside `data/` or designated paths under `/etc/kubernetes`.
- Do not commit files excluded by `.gitignore` (e.g. `certs/cert_info.json`, `data/collected_info.json`).

## Adding a new script

- Place your script in the relevant folder (`setup/`, `certs/`, `kubeadm/`, etc.).
- Add its invocation to `main.py` at the appropriate step.
- Use `log("[STEP] <описание операции>")` so the output style remains consistent.

## Validation

There are no automated tests. Before committing changes to Python files, run:

```bash
python -m py_compile $(git ls-files '*.py')
```

This ensures all scripts compile without syntax errors.
