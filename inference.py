import os
import sys
import json
import time
from openai import OpenAI

API_BASE_URL = os.environ.get("API_BASE_URL", "https://openrouter.ai/api/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "openai/gpt-oss-120b:free")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:7860")

llm = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN if HF_TOKEN else "no-key-needed",
)

SYSTEM_PROMPT = """You are CodeSentinel, an expert security-focused code reviewer. Find ALL bugs in the code.

Output ONLY a JSON object with this exact structure, no markdown, no extra text:
{
  "action_type": "submit_findings",
  "findings": [
    {
      "line_range": "LINE_NUMBER or START-END",
      "description": "Clear explanation of the bug and its impact",
      "severity": "P0, P1, P2, or P3",
      "suggested_fix": "Brief fix"
    }
  ]
}

Severity: P0=security/auth/data loss, P1=race condition/corruption, P2=logic error/null check/off-by-one, P3=minor
Output ONLY valid JSON."""


def build_review_prompt(code_snippet, task_description, additional_context):
    return f"Task:\n{task_description}\n\nCode:\n```\n{code_snippet}\n```\n\nContext:\n{additional_context or 'None'}\n\nFind all bugs. Output JSON only."


def parse_llm_response(text):
    text = text.strip()
    try:
        return json.loads(text)
    except:
        pass
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except:
        pass
    return {"action_type": "submit_findings", "findings": []}


def call_server(method, path, **kwargs):
    import urllib.request
    import urllib.error

    url = SERVER_URL.rstrip("/") + path
    data = json.dumps(kwargs.get("json", {})).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def run_task(task_id):
    print(f"[START] task={task_id}", flush=True)
    sys.stdout.flush()

    obs = call_server(
        "POST", "/reset", json={"session_id": task_id, "task_id": task_id}
    )
    print(f"[STEP] step=1 reward=0.0 done=False", flush=True)
    sys.stdout.flush()

    context_resp = call_server(
        "POST",
        "/step",
        json={
            "session_id": task_id,
            "action": {
                "action_type": "request_context",
                "context_question": "What is the production context?",
            },
        },
    )
    print(f"[STEP] step=2 reward=0.0 done=False", flush=True)
    sys.stdout.flush()

    code_snippet = obs.get("code_snippet", "")
    task_description = obs.get("task_description", "")
    additional_context = context_resp.get("additional_context", "")

    prompt = build_review_prompt(code_snippet, task_description, additional_context)

    try:
        response = llm.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1500,
        )
        response_text = response.choices[0].message.content
    except Exception as e:
        print(f"[STEP] step=3 reward=0.0 done=True", flush=True)
        print(f"[END] task={task_id} score=0.0 steps=3", flush=True)
        sys.stdout.flush()
        return 0.0

    parsed = parse_llm_response(response_text)
    findings = parsed.get("findings", [])

    submit_resp = call_server(
        "POST",
        "/step",
        json={
            "session_id": task_id,
            "action": {"action_type": "submit_findings", "findings": findings},
        },
    )

    score = submit_resp.get("reward", 0.0)
    score = float(score)
    if score <= 0.0:
        score = 0.01
    if score >= 1.0:
        score = 0.99
    score = round(score, 4)
    print(f"[STEP] step=3 reward={score} done=True", flush=True)
    print(f"[END] task={task_id} score={score} steps=3", flush=True)
    sys.stdout.flush()
    return score


if __name__ == "__main__":
    print(f"[START] task=codesentinel_eval", flush=True)
    sys.stdout.flush()

    scores = {}
    for task_id in ["easy_review", "medium_review", "hard_review"]:
        score = run_task(task_id)
        scores[task_id] = score
        time.sleep(1)

    avg = round(sum(scores.values()) / len(scores), 3)
    print(f"[END] task=codesentinel_eval score={avg} steps=9", flush=True)
    sys.stdout.flush()

    print("\n========== FINAL RESULTS ==========", flush=True)
    for k, v in scores.items():
        print(f"{k}: {v}", flush=True)
    print(f"Average score: {avg}", flush=True)
    print("====================================", flush=True)
