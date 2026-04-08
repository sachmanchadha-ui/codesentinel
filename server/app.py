import os
import sys
import json
import asyncio
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import CodeReviewAction, CodeReviewObservation, CodeReviewState
from server.environment import CodeSentinelEnvironment

app = FastAPI(
    title="CodeSentinel",
    description="Automated code review RL environment for the Meta PyTorch OpenEnv Hackathon",
    version="0.1.0",
)

sessions: dict = {}


def get_or_create_session(session_id: str) -> CodeSentinelEnvironment:
    if session_id not in sessions:
        sessions[session_id] = CodeSentinelEnvironment()
    return sessions[session_id]


class ResetRequest(BaseModel):
    session_id: str = "default"
    task_id: Optional[str] = None


class StepRequest(BaseModel):
    session_id: str = "default"
    action: dict = {}


@app.get("/")
async def root():
    return JSONResponse(
        {"status": "ok", "environment": "CodeSentinel", "version": "0.1.0"}
    )


@app.get("/health")
async def health():
    return JSONResponse({"status": "healthy"})


@app.post("/reset")
async def reset(request: Optional[ResetRequest] = None):
    if request is None:
        request = ResetRequest()
    env = get_or_create_session(request.session_id)
    obs = env.reset(task_id=request.task_id)
    return obs.model_dump()


@app.post("/step")
async def step_endpoint(request: StepRequest):
    env = get_or_create_session(request.session_id)
    try:
        action = CodeReviewAction(**request.action)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    obs = env.step(action)
    return obs.model_dump()


@app.get("/state")
async def state_endpoint(session_id: str = "default"):
    env = get_or_create_session(session_id)
    try:
        state = env.state
        return state.model_dump()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail="Call /reset first")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    env = CodeSentinelEnvironment()  # Dedicated environment per WS connection
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                method = msg.get("method")
                params = msg.get("params", {})

                if method == "reset":
                    task_id = params.get("task_id", None)
                    obs = env.reset(task_id=task_id)
                    await websocket.send_text(json.dumps({"result": obs.model_dump()}))
                elif method == "step":
                    action = CodeReviewAction(**params.get("action", {}))
                    obs = env.step(action)
                    await websocket.send_text(json.dumps({"result": obs.model_dump()}))
                elif method == "state":
                    try:
                        state = env.state
                        await websocket.send_text(
                            json.dumps({"result": state.model_dump()})
                        )
                    except RuntimeError as e:
                        await websocket.send_text(json.dumps({"error": str(e)}))
                else:
                    await websocket.send_text(
                        json.dumps({"error": f"Unknown method: {method}"})
                    )
            except json.JSONDecodeError as e:
                await websocket.send_text(
                    json.dumps({"error": f"Invalid JSON: {str(e)}"})
                )
            except Exception as e:
                await websocket.send_text(json.dumps({"error": str(e)}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
        except:
            pass  # Connection might already be closed


@app.on_event("startup")
async def startup():
    print("CodeSentinel environment server started.")
    print(
        "Endpoints: GET / | GET /health | POST /reset | POST /step | GET /state | WS /ws"
    )


def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()
