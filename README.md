# AgentCloud

CPU-only, simulated **autonomous incident response** demo using an agentic pipeline:

`Log Generator → Monitoring → Diagnosis → Planning → Execution → Memory`

This repository is intentionally lightweight and runnable without a GPU.

## Quickstart

```bash
python3 -m agentcloud.main --scenario mixed --max-events 5
```

Logs are written to `logs/cloud.jsonl`. Long-term incident memory is stored in `database.db` (SQLite).

## Scenarios

- `normal`
- `overload`
- `intrusion`
- `crash`
- `mixed` (default)

## What to expect in the demo

You’ll see:

- log generation
- anomaly alerts
- structured diagnosis
- planned mitigation action
- simulated execution result
- memory writes (and reuse of past successful plans)

To print raw simulator logs as well:

```bash
python3 -m agentcloud.main --scenario mixed --max-events 5 --show-logs
```

## Ablations (for the report)

```bash
# Without memory
python3 -m agentcloud.main --scenario mixed --max-events 5 --no-memory

# Without planning agent
python3 -m agentcloud.main --scenario mixed --max-events 5 --no-planning
```

## LLM diagnosis (optional)

By default, diagnosis uses a deterministic CPU-only fallback. To enable LLM-based reasoning:

```bash
export OPENAI_API_KEY="..."
export AGENTCLOUD_LLM_MODEL="gpt-4o-mini"
python3 -m agentcloud.main --scenario mixed --max-events 5
```

### Local LLM (no API, CPU-only)

Install llama.cpp bindings:

```bash
python3 -m pip install llama-cpp-python
```

Download a GGUF model (example: any small instruct GGUF) and set:

```bash
export AGENTCLOUD_LOCAL_MODEL_PATH="/path/to/model.gguf"
python3 -m agentcloud.main --scenario mixed --max-events 5
```

## Trace output (JSONL)

```bash
python3 -m agentcloud.main --scenario mixed --max-events 5 --trace-file logs/trace.jsonl
```

## Failure → recovery learning demo

For a report-friendly demo that forces a failure first and then recovers using memory:

```bash
python3 -m agentcloud.main --demo-learning --tick 0.02 --trace-file logs/trace.jsonl
```

## Evaluation runner (quick metrics)

```bash
python3 -m agentcloud.evaluation --scenario mixed --episodes 10 --max-incidents 5
python3 -m agentcloud.evaluation --scenario mixed --episodes 10 --max-incidents 5 --no-memory
python3 -m agentcloud.evaluation --scenario mixed --episodes 10 --max-incidents 5 --no-planning
```

