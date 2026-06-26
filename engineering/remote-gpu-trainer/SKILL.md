---
name: "remote-gpu-trainer"
description: "Provision, configure, and run distributed ML training jobs on remote GPU instances. Use when fine-tuning LLMs, training vision models, or running any job that exceeds local GPU memory or would take more than 4 hours on a single machine."
---

# Remote GPU Trainer

## Overview

This skill covers the end-to-end workflow for remote GPU training: choosing a provider, provisioning instances, setting up distributed training, managing checkpoints, monitoring runs, and shutting down without leaving orphaned resources. It is framework-agnostic but provides concrete examples for PyTorch (DDP, FSDP) and Hugging Face Accelerate.

## Core Content

### Phase 1 — Choose a provider

| Provider | Best for | Spot/interruptible | Min $/hr (H100) |
|----------|----------|---------------------|-----------------|
| Lambda Labs | Long fine-tunes, reserved | No | ~$2.49 |
| Vast.ai | Budget spot, research | Yes | ~$1.50 |
| RunPod | Balanced, community pods | Yes | ~$1.99 |
| AWS p4d / p5 | Production, compliance | Yes (Spot) | ~$3.80 |
| GCP A3 | TPU access too | Yes (Preemptible) | ~$3.90 |
| CoreWeave | H100/A100 clusters | Yes | ~$2.20 |

Use spot/interruptible instances only when your training is checkpoint-resumable (see Phase 4). For a first run, use on-demand to establish a baseline cost before optimising.

### Phase 2 — Provision and configure

Never manually SSH-configure a fleet. Use a reproducible setup script:

```bash
#!/usr/bin/env bash
# setup.sh — runs on every node after provisioning
set -euo pipefail

# 1. System packages
apt-get update -qq && apt-get install -y -q git wget tmux htop nvtop

# 2. Python environment (prefer uv for speed)
pip install -q uv
uv venv /workspace/venv --python 3.11
source /workspace/venv/bin/activate

# 3. Project dependencies (stdlib-free for the trainer, but ML stack is exempt)
uv pip install -r requirements.txt

# 4. Verify GPU visibility
python3 -c "import torch; assert torch.cuda.device_count() > 0, 'No CUDA GPUs visible'; print(f'{torch.cuda.device_count()} GPU(s) ready')"
```

Store `setup.sh` in the repo. Run it on every node before training starts.

### Phase 3 — Multi-node distributed training

For multi-GPU / multi-node runs, use `torchrun` (PyTorch ≥ 1.11):

```bash
# Single node, 8 GPUs
torchrun --nproc-per-node=8 train.py --config config.yaml

# Multi-node (run on each node; set MASTER_ADDR to node-0's IP)
torchrun \
  --nproc-per-node=8 \
  --nnodes=2 \
  --node-rank=${NODE_RANK} \
  --master-addr=${MASTER_ADDR} \
  --master-port=29500 \
  train.py --config config.yaml
```

Use **FSDP** (Fully Sharded Data Parallel) for models > 7B parameters. Use **DDP** for smaller models — it has lower communication overhead.

```python
# Minimal FSDP wrapper — wrap before the optimizer
from torch.distributed.fsdp import FullyShardedDataParallel as FSDP
model = FSDP(model, auto_wrap_policy=transformer_auto_wrap_policy)
```

For HuggingFace models, prefer `accelerate` — it handles DDP/FSDP/DeepSpeed transparently:

```bash
accelerate config   # interactive setup, generates accelerate_config.yaml
accelerate launch --config_file accelerate_config.yaml train.py
```

### Phase 4 — Checkpoint strategy (mandatory for spot instances)

Checkpoint every N steps, not every epoch. On spot instances, N ≤ 500 is safe:

```python
if global_step % CHECKPOINT_EVERY == 0:
    # Save model + optimizer + scheduler + RNG state
    accelerator.save_state(f"checkpoints/step-{global_step}")

# Resume: pass output_dir to load_state at training start
if Path("checkpoints").exists():
    latest = max(Path("checkpoints").glob("step-*"), key=lambda p: int(p.name.split("-")[1]))
    accelerator.load_state(str(latest))
```

Store checkpoints to persistent storage (S3, GCS, NFS) — not the instance's local disk, which is lost on spot eviction. Use `rclone` or `s5cmd` to sync checkpoints to object storage after every save.

### Phase 5 — Monitor the run

Always run these in parallel with training:

```bash
# GPU utilisation (should be > 85 % on forward pass)
watch -n2 nvidia-smi

# Live loss curve — pipe trainer output through tee
python train.py 2>&1 | tee run.log

# Estimate remaining time from log
grep "step" run.log | tail -1
```

For longer runs, integrate Weights & Biases or MLflow:

```python
# W&B — minimal setup
import wandb
wandb.init(project="my-model", config=vars(args))
wandb.log({"loss": loss.item(), "step": global_step})
```

### Phase 6 — Tear down immediately

A running instance with no training job costs the same as one actively training. Add a shutdown hook:

```python
import subprocess, atexit

def _teardown():
    subprocess.run(["python3", "scripts/release-instance.py", "--instance-id", INSTANCE_ID], check=False)

atexit.register(_teardown)
```

Use `scripts/teardown-gpu.py` for provider-agnostic instance termination.

> See [references/provider-apis.md](references/provider-apis.md) for CLI commands to terminate instances on Lambda, Vast.ai, RunPod, AWS, and GCP.

### Cost estimation before you start

```bash
python3 scripts/estimate-cost.py \
  --hours 12 \
  --gpus 8 \
  --provider lambdalabs \
  --gpu-type h100
# → Estimated cost: $238.80
```

Never start a multi-hour run without a written estimate. GPU time is the largest ML training cost and it compounds with misconfiguration.

## Anti-Patterns

**Never train without checkpointing.** A 10-hour run without checkpoints that gets interrupted by a preemption or OOM is a 10-hour loss.

**Never block on `pip install` inside the training loop.** All dependencies must be installed in `setup.sh` before the job starts.

**Never store credentials in training scripts.** Use IAM roles (AWS), Workload Identity (GCP), or environment variables injected by the orchestration layer — never hardcode keys.

**Never run multi-node training without verifying connectivity first.** Run `torchrun --nnodes=2 test_comm.py` (a no-op `all_reduce`) before starting the real job.

**Never ignore GPU utilisation below 70 %.** Low utilisation means your data pipeline is the bottleneck. Profile with `torch.profiler` and fix the DataLoader before spending money on compute.

**Never leave instances running overnight.** Set a budget alert and a cron-triggered teardown. One forgotten H100 × 8 hours = ~$20 wasted.

## Cross-References

- [engineering/llm-cost-optimizer](../llm-cost-optimizer/SKILL.md) — reduce inference cost after training completes
- [engineering/docker-development](../docker-development/SKILL.md) — containerise training environments for reproducibility
- [engineering/slo-architect](../slo-architect/SKILL.md) — define training-job SLOs (completion time, cost ceiling)
- [engineering/terraform-patterns](../terraform-patterns/SKILL.md) — provision GPU clusters declaratively
- [engineering/observability-and-instrumentation](../observability-and-instrumentation/SKILL.md) — instrument training jobs for production monitoring
