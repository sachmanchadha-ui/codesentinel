try:
    from openenv.core.env_server import Action, Observation, State
except ImportError:
    from pydantic import BaseModel

    class Action(BaseModel):
        pass

    class Observation(BaseModel):
        done: bool = False
        reward: float = 0.0

    class State(BaseModel):
        pass


from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class Finding(BaseModel):
    line_range: str = Field(
        description="Line or range of lines where bug exists, e.g. '12' or '23-27'"
    )
    description: str = Field(
        description="Clear description of the bug and why it is a problem"
    )
    severity: Literal["P0", "P1", "P2", "P3"] = Field(
        description="P0=critical security/data loss, P1=high impact, P2=medium functional bug, P3=low/style"
    )
    suggested_fix: Optional[str] = Field(
        default=None, description="Optional suggested code fix"
    )


class CodeReviewAction(Action):
    action_type: Literal["request_context", "submit_findings"] = Field(
        description="request_context to ask for more info, submit_findings to submit your bug report"
    )
    context_question: Optional[str] = Field(
        default=None,
        description="Your question about the codebase or requirements (only used when action_type is request_context)",
    )
    findings: Optional[List[Finding]] = Field(
        default=None,
        description="Your list of identified bugs (only used when action_type is submit_findings)",
    )


class CodeReviewObservation(Observation):
    code_snippet: str = Field(description="The code snippet to review")
    task_description: str = Field(
        description="What this code is supposed to do and its context"
    )
    additional_context: Optional[str] = Field(
        default=None, description="Response to your context request, if any"
    )
    steps_taken: int = Field(
        default=0, description="How many steps you have taken in this episode"
    )
    max_steps: int = Field(
        default=3, description="Maximum steps allowed before episode ends"
    )
    done: bool = Field(default=False, description="True when episode is complete")
    reward: float = Field(
        default=0.0,
        description="Your score so far (0.0 until submission, then final score)",
    )
    message: str = Field(
        default="", description="Feedback message from the environment"
    )


class CodeReviewState(State):
    task_id: str = Field(description="Which task is currently loaded")
    planted_bugs: List[dict] = Field(
        default_factory=list, description="Ground truth bugs — never sent to agent"
    )
    steps_taken: int = Field(default=0)
    max_steps: int = Field(default=3)
    context_requests: List[str] = Field(
        default_factory=list, description="Questions the agent has asked"
    )
    context_responses: List[str] = Field(
        default_factory=list, description="Answers given to agent questions"
    )
    submitted: bool = Field(default=False)
    final_score: float = Field(default=0.0)
