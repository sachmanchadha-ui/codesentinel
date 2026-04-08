import os
import json
import time
from openai import OpenAI
from client import CodeSentinelClient
from models import CodeReviewAction, Finding

# ENV VAR LOADING (at top, before any functions)
API_BASE_URL = os.environ.get("API_BASE_URL", "https://openrouter.ai/api/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "openai/gpt-oss-120b:free")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:7860")

# LLM CLIENT SETUP
llm = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN if HF_TOKEN else "no-key-needed",
)

# SYSTEM PROMPT CONSTANT
SYSTEM_PROMPT = """You are CodeSentinel, an expert security-focused code reviewer. Your job is to find bugs, vulnerabilities, and logic errors in code snippets.

When reviewing code, you MUST output a JSON object with this exact structure:
{
  "action_type": "submit_findings",
  "findings": [
    {
      "line_range": "LINE_NUMBER or START-END",
      "description": "Clear explanation of the bug and its impact",
      "severity": "P0, P1, P2, or P3",
      "suggested_fix": "Brief suggested fix"
    }
  ]
}

Severity guide:
- P0: Critical — security vulnerability, data loss, authentication bypass
- P1: High — race condition, data corruption, broken core functionality  
- P2: Medium — incorrect logic, missing null check, wrong output
- P3: Low — style issue, minor inefficiency

Rules:
- Report ALL bugs you find, even minor ones
- Be specific about line numbers
- severity field must be exactly P0, P1, P2, or P3
- Output ONLY valid JSON, no markdown, no explanation outside the JSON"""


def build_review_prompt(obs) -> str:
    """Build a prompt for the LLM based on the observation."""
    return f"""Task description:
{obs.task_description}

Code to review:
```
{obs.code_snippet}
```

Additional context:
{obs.additional_context if obs.additional_context else "None provided"}

Analyze the code carefully. Find all bugs. Output your findings as JSON."""


def parse_llm_response(response_text: str) -> CodeReviewAction:
    """Parse the LLM response into a CodeReviewAction."""
    # Strip response_text of whitespace
    response_text = response_text.strip()

    # Try json.loads(response_text) directly
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        # Try to find JSON between first { and last }
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start != -1 and end != -1 and start < end:
            json_str = response_text[start : end + 1]
            try:
                parsed = json.loads(json_str)
            except json.JSONDecodeError:
                # If parsing still fails: return empty findings
                return CodeReviewAction(action_type="submit_findings", findings=[])
        else:
            # If parsing still fails: return empty findings
            return CodeReviewAction(action_type="submit_findings", findings=[])

    # From parsed dict:
    action_type = parsed.get("action_type", "submit_findings")
    raw_findings = parsed.get("findings", [])
    findings = []

    # For each f in raw_findings:
    for f in raw_findings:
        try:
            findings.append(
                Finding(
                    line_range=str(f.get("line_range", "0")),
                    description=f.get("description", ""),
                    severity=f.get("severity", "P3"),
                    suggested_fix=f.get("suggested_fix", None),
                )
            )
        except Exception:
            continue  # Skip invalid findings

    return CodeReviewAction(action_type="submit_findings", findings=findings)


def run_task(client: CodeSentinelClient, task_id: str, llm: OpenAI) -> dict:
    print(f"[START] task={task_id}", flush=True)

    obs = client.reset(task_id=task_id)
    print(f"[STEP] step=1 reward=0.0 done=False", flush=True)

    context_action = CodeReviewAction(
        action_type="request_context",
        context_question="What is the production context and any known constraints for this code?",
    )
    obs = client.step(context_action)
    print(f"[STEP] step=2 reward={obs.reward} done={obs.done}", flush=True)

    prompt = build_review_prompt(obs)
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
        return {"task_id": task_id, "score": 0.0, "message": str(e)}

    action = parse_llm_response(response_text)
    obs = client.step(action)
    print(f"[STEP] step=3 reward={obs.reward} done={obs.done}", flush=True)
    print(f"[END] task={task_id} score={obs.reward} steps=3", flush=True)

    return {"task_id": task_id, "score": obs.reward, "message": obs.message}


if __name__ == "__main__":
    print("CodeSentinel Inference Script")
    print(f"Model: {MODEL_NAME}")
    print(f"Server: {SERVER_URL}")
    print(f"API: {API_BASE_URL}")

    client = CodeSentinelClient(base_url=SERVER_URL)

    # Health check
    if not client.health():
        print("ERROR: Server not reachable. Start it with: python server/app.py")
        exit(1)

    print("Server is healthy. Starting evaluation...")
    start_time = time.time()

    results = []
    for task_id in ["easy_review", "medium_review", "hard_review"]:
        result = run_task(client, task_id, llm)
        results.append(result)
        time.sleep(2)  # Avoid rate limiting

    print("\n========== FINAL RESULTS ==========")
    total = 0.0
    for r in results:
        print(f"{r['task_id']}: {r['score']}")
        total += r["score"]
    avg = round(total / len(results), 3)
    print(f"Average score: {avg}")
    print(f"Total time: {round(time.time() - start_time, 1)}s")
    print("====================================")

    client.close()
