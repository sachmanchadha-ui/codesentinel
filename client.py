import json
import asyncio
from typing import Optional
import httpx
from models import CodeReviewAction, CodeReviewObservation, CodeReviewState


class CodeSentinelClient:
    def __init__(
        self, base_url: str = "http://localhost:7860", session_id: str = "default"
    ):
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id
        self._client = httpx.Client(timeout=60.0)

    def reset(self, task_id: Optional[str] = None) -> CodeReviewObservation:
        response = self._client.post(
            f"{self.base_url}/reset",
            json={"session_id": self.session_id, "task_id": task_id},
        )
        response.raise_for_status()
        return CodeReviewObservation.model_validate(response.json())

    def step(self, action: CodeReviewAction) -> CodeReviewObservation:
        response = self._client.post(
            f"{self.base_url}/step",
            json={"session_id": self.session_id, "action": action.model_dump()},
        )
        response.raise_for_status()
        return CodeReviewObservation.model_validate(response.json())

    def state(self) -> CodeReviewState:
        response = self._client.get(
            f"{self.base_url}/state", params={"session_id": self.session_id}
        )
        response.raise_for_status()
        return CodeReviewState.model_validate(response.json())

    def health(self) -> bool:
        try:
            response = self._client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
