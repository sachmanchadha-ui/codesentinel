import random
import sys
import os
from typing import Optional, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import CodeReviewAction, CodeReviewObservation, CodeReviewState, Finding
from server.scenarios import SCENARIOS
from server.grader import grade_from_models

try:
    from openenv.core.env_server import Environment
except ImportError:

    class Environment:
        pass


class CodeSentinelEnvironment(Environment):
    MAX_STEPS = 3
    TASK_IDS = ["easy_review", "medium_review", "hard_review"]

    def __init__(self):
        self._state: Optional[CodeReviewState] = None
        self._scenario: Optional[dict] = None
        self._task_id: Optional[str] = None

    def reset(self, task_id: Optional[str] = None) -> CodeReviewObservation:
        if task_id is None or task_id not in SCENARIOS:
            task_id = random.choice(self.TASK_IDS)

        scenario = SCENARIOS[task_id]
        self._task_id = task_id
        self._scenario = scenario
        self._state = CodeReviewState(
            task_id=task_id,
            planted_bugs=scenario["planted_bugs"],
            steps_taken=0,
            max_steps=self.MAX_STEPS,
            context_requests=[],
            context_responses=[],
            submitted=False,
            final_score=0.0,
        )

        return CodeReviewObservation(
            code_snippet=scenario["code_snippet"],
            task_description=scenario["task_description"],
            additional_context=None,
            steps_taken=0,
            max_steps=self.MAX_STEPS,
            done=False,
            reward=0.0,
            message="Environment ready. Review the code and either request context or submit your findings.",
        )

    def step(self, action: CodeReviewAction) -> CodeReviewObservation:
        if self._state is None:
            raise RuntimeError("Call reset() before step()")

        if self._state.submitted or self._state.steps_taken >= self.MAX_STEPS:
            return CodeReviewObservation(
                code_snippet=self._scenario["code_snippet"],
                task_description=self._scenario["task_description"],
                additional_context=None,
                steps_taken=self._state.steps_taken,
                max_steps=self.MAX_STEPS,
                done=True,
                reward=self._state.final_score,
                message="Episode already complete.",
            )

        self._state.steps_taken += 1
        steps_left = self.MAX_STEPS - self._state.steps_taken

        if action.action_type == "request_context":
            if len(self._state.context_requests) >= 1:
                context_response = "You have already requested context once. Please submit your findings now."
            else:
                context_response = self._scenario.get(
                    "additional_context", "No additional context available."
                )

            context_question = action.context_question or "context requested"
            self._state.context_requests.append(context_question)
            self._state.context_responses.append(context_response)

            done = steps_left <= 0
            if done:
                self._force_submit()
                reward = self._state.final_score
            else:
                reward = 0.0

            return CodeReviewObservation(
                code_snippet=self._scenario["code_snippet"],
                task_description=self._scenario["task_description"],
                additional_context=context_response,
                steps_taken=self._state.steps_taken,
                max_steps=self.MAX_STEPS,
                done=done,
                reward=reward,
                message=f"Context provided. {steps_left} step(s) remaining."
                if not done
                else "Out of steps. Episode ended.",
            )

        elif action.action_type == "submit_findings":
            findings = action.findings or []
            result = grade_from_models(self._task_id, findings)
            self._state.final_score = result["score"]
            self._state.submitted = True
            breakdown_msg = f"Bugs found: {result['bugs_found']}/{result['bugs_total']}. Score: {result['score']}"

            return CodeReviewObservation(
                code_snippet=self._scenario["code_snippet"],
                task_description=self._scenario["task_description"],
                additional_context=None,
                steps_taken=self._state.steps_taken,
                max_steps=self.MAX_STEPS,
                done=True,
                reward=result["score"],
                message=breakdown_msg,
            )

        else:
            return CodeReviewObservation(
                code_snippet=self._scenario["code_snippet"],
                task_description=self._scenario["task_description"],
                additional_context=None,
                steps_taken=self._state.steps_taken,
                max_steps=self.MAX_STEPS,
                done=False,
                reward=0.0,
                message="Unknown action type.",
            )

    def _force_submit(self) -> None:
        result = grade_from_models(self._task_id, [])
        self._state.final_score = result["score"]
        self._state.submitted = True

    @property
    def state(self) -> CodeReviewState:
        if self._state is None:
            raise RuntimeError("Call reset() first")
        return self._state
