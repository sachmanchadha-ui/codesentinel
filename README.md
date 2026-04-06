---
title: CodeSentinel
emoji: 🔍
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
---
# CodeSentinel — Automated Code Review RL Environment

An OpenEnv-compliant reinforcement learning environment where an LLM agent reviews real-world code snippets, identifies planted bugs, classifies their severity, and suggests fixes. Built for the Meta PyTorch OpenEnv Hackathon.

## Environment Description

CodeSentinel presents an agent with realistic code snippets containing deliberately planted bugs. The agent must:
1. Optionally request additional context about the codebase (1 context request allowed)
2. Submit findings: a list of bugs with line numbers, severity (P0-P3), and descriptions
3. Receive a deterministic score based on how many bugs it found and how accurately it classified them

## Action Space
```json
{
  "action_type": "request_context | submit_findings",
  "context_question": "optional string (used with request_context)",
  "findings": [
    {
      "line_range": "9 or 23-27",
      "description": "description of the bug",
      "severity": "P0 | P1 | P2 | P3",
      "suggested_fix": "optional fix"
    }
  ]
}
```

## Observation Space
```json
{
  "code_snippet": "string",
  "task_description": "string",
  "additional_context": "string or null",
  "steps_taken": 0,
  "max_steps": 3,
  "done": false,
  "reward": 0.0,
  "message": "string"
}
```

## Tasks

| Task ID | Difficulty | Language | Bugs | Description |
|---|---|---|---|---|
| easy_review | Easy | Python | 2 | Off-by-one + missing null guard |
| medium_review | Medium | JavaScript | 2 | Race condition + swallowed exception |
| hard_review | Hard | Python | 3 | SQL injection + missing auth + type error |

## Reward Function

- Exact location match (within ±2 lines): full bug weight
- Keyword match only (no location): 50% of bug weight  
- Correct severity classification: up to 10% bonus per bug
- All scores strictly in [0.0, 1.0]

## Setup Instructions

### Prerequisites
- Python 3.11+
- pip or uv

### Install dependencies
```bash
pip install fastapi uvicorn pydantic websockets openai python-dotenv httpx openenv-core
```

### Environment Variables
| Variable | Description | Example |
|---|---|---|
| API_BASE_URL | OpenAI-compatible API endpoint | https://openrouter.ai/api/v1 |
| MODEL_NAME | Model identifier | openai/gpt-oss-120b:free |
| HF_TOKEN | Your API key | sk-or-... |

### Run the server
```bash
python -m uvicorn server.app:app --host 0.0.0.0 --port 7860
```

### Run inference
```bash
export API_BASE_URL=https://openrouter.ai/api/v1
export MODEL_NAME=openai/gpt-oss-120b:free
export HF_TOKEN=your_key_here
python inference.py
```

### Run with Docker
```bash
docker build -t codesentinel -f server/Dockerfile .
docker run -p 7860:7860 \
  -e API_BASE_URL=https://openrouter.ai/api/v1 \
  -e MODEL_NAME=openai/gpt-oss-120b:free \
  -e HF_TOKEN=your_key_here \
  codesentinel
```

## Baseline Scores

| Task | Score |
|---|---|
| easy_review | 1.0 |
| medium_review | ≥0.8 |
| hard_review | ≥0.7 |
| Average | ≥0.83 |

## HF Space
https://huggingface.co/spaces/sachman09/codesentinel