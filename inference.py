import os
import sys
import json
import time
import urllib.request

API_BASE_URL = os.environ.get("API_BASE_URL", "https://openrouter.ai/api/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "openai/gpt-oss-120b:free")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:7860")
BENCHMARK = "codesentinel"

SYSTEM_PROMPT = """You are CodeSentinel, an expert security engineer and code reviewer. Find ALL bugs in the code.

Output ONLY a valid JSON object. No markdown. No text outside JSON.

{
  "action_type": "submit_findings",
  "findings": [
    {
      "line_range": "16",
      "description": "SQL injection via f-string interpolation of user_id into query",
      "severity": "P0",
      "suggested_fix": "Use parameterized query: cursor.execute('SELECT * FROM rewards WHERE user_id = ?', (user_id,))"
    }
  ]
}

Severity:
P0 = SQL injection, missing auth, remote code execution, data breach
P1 = Race condition, data corruption, unhandled crash
P2 = Off-by-one, missing null/empty check, division by zero, wrong type
P3 = Minor inefficiency, style

RULES:
- Report every bug found
- Line numbers must be specific
- SQL injection via f-string is always P0
- Missing auth decorator on admin endpoint is always P0
- Race condition on shared mutable state is always P1
- Off-by-one in slice like [:n+1] is always P2
- Missing null/empty check before sum/division is always P2
- request.args value used in math without type cast is always P1
- Empty except/catch block swallowing errors is always P2
- Output ONLY the JSON object"""


def clamp(score):
    try:
        s = float(score)
    except:
        return 0.05
    if s <= 0.0:
        return 0.05
    if s >= 1.0:
        return 0.95
    return round(s, 2)


def log_start(task):
    print(f"[START] task={task} env={BENCHMARK} model={MODEL_NAME}", flush=True)


def log_step(step, action, reward, done, error=None):
    r = f"{float(reward):.2f}"
    d = "true" if done else "false"
    e = error if error else "null"
    a = str(action).replace("\n", " ")[:80]
    print(f"[STEP] step={step} action={a} reward={r} done={d} error={e}", flush=True)


def log_end(success, steps, score, rewards):
    s = f"{float(score):.2f}"
    rs = ",".join(f"{float(r):.2f}" for r in rewards)
    succ = "true" if success else "false"
    print(f"[END] success={succ} steps={steps} score={s} rewards={rs}", flush=True)


def call_server(method, path, body=None):
    url = SERVER_URL.rstrip("/") + path
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        sys.stderr.write(f"Server error: {e}\n")
        return {}


def call_llm(prompt):
    try:
        from openai import OpenAI

        client = OpenAI(
            base_url=API_BASE_URL, api_key=HF_TOKEN if HF_TOKEN else "no-key"
        )
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=2000,
        )
        return resp.choices[0].message.content
    except Exception as e:
        sys.stderr.write(f"LLM error: {e}\n")
        return None


def parse_findings(text):
    if not text:
        return []
    text = text.strip()
    for attempt in [text, text[text.find("{") : text.rfind("}") + 1]]:
        try:
            return json.loads(attempt).get("findings", [])
        except:
            continue
    return []


def run_task(task_id):
    rewards = []
    log_start(task_id)

    obs = call_server("POST", "/reset", {"session_id": task_id, "task_id": task_id})
    reset_reward = obs.get("reward", 0.0)
    log_step(1, "reset", reset_reward, False)
    rewards.append(reset_reward)

    ctx = call_server(
        "POST",
        "/step",
        {
            "session_id": task_id,
            "action": {
                "action_type": "request_context",
                "context_question": "What is the production environment, authentication requirements, concurrency model, and known constraints?",
            },
        },
    )
    ctx_reward = ctx.get("reward", 0.0)
    log_step(2, "request_context", ctx_reward, False)
    rewards.append(ctx_reward)

    code = obs.get("code_snippet", "")
    desc = obs.get("task_description", "")
    context = ctx.get("additional_context", "") or "None provided"

    prompt = f"""Task description:
{desc}

Code to review:Production context:
{context}

Find ALL bugs. Be specific about line numbers. Output ONLY the JSON findings object."""

    llm_text = call_llm(prompt)
    findings = parse_findings(llm_text)
    sys.stderr.write(f"{task_id}: {len(findings)} findings parsed\n")

    submit = call_server(
        "POST",
        "/step",
        {
            "session_id": task_id,
            "action": {"action_type": "submit_findings", "findings": findings},
        },
    )

    raw = submit.get("reward", 0.0)
    score = clamp(raw)
    sys.stderr.write(f"{task_id}: raw={raw} clamped={score}\n")

    rewards.append(score)
    log_step(3, "submit_findings", score, True)
    log_end(score > 0.1, 3, score, rewards)
    return score


if __name__ == "__main__":
    sys.stderr.write(f"Starting CodeSentinel. Model={MODEL_NAME} Server={SERVER_URL}\n")

    all_scores = {}
    for task_id in ["easy_review", "medium_review", "hard_review"]:
        try:
            s = run_task(task_id)
            all_scores[task_id] = s
        except Exception as e:
            sys.stderr.write(f"{task_id} crashed: {e}\n")
            all_scores[task_id] = 0.05
            log_end(False, 3, 0.05, [0.05, 0.05, 0.05])
        time.sleep(2)

    avg = clamp(sum(all_scores.values()) / len(all_scores))
    sys.stderr.write(f"\n=== RESULTS ===\n")
    for k, v in all_scores.items():
        sys.stderr.write(f"{k}: {v}\n")
    sys.stderr.write(f"Average: {avg}\n")
