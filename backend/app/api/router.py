from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from ..domain.types import ConfigurationSaveRequest, ManualCommandRequest, OperatorRequest, ResetConfigurationRequest, StateVersionRequest
from ..orchestration.controller import AFDSController


class RuntimeInfo(BaseModel):
    application: str = "AFDS"
    version: str = "1.0.0"
    runtimeMode: str = "HARDWARE"
    operationModes: list[str] = ["AUTOMATIC", "MANUAL"]
    simulationAvailable: bool = False
    physicalDemoAutomationAvailable: bool = False


class EstopRequest(BaseModel):
    operator: str = Field(min_length=1, max_length=80)


def create_router(controller: AFDSController) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/runtime")
    async def runtime_info() -> dict[str, Any]:
        return RuntimeInfo().model_dump()

    @router.get("/health")
    async def health() -> dict[str, Any]:
        snapshot = controller.snapshot()
        return {"status": "ok", "backend": True, "hardware": snapshot["hardware"]["connected"], "vision": snapshot["vision"]["ready"], "state": snapshot["state"]}

    @router.get("/state")
    async def state() -> dict[str, Any]:
        return controller.snapshot()

    @router.post("/system/initialize")
    async def initialize(request: OperatorRequest) -> dict[str, Any]:
        return await controller.initialize(request.operator, request.expected_state_version)

    @router.post("/automatic/start")
    async def start_automatic(request: OperatorRequest) -> dict[str, Any]:
        return await controller.start_automatic(request.operator, request.expected_state_version)

    @router.post("/control/pause")
    async def pause(request: StateVersionRequest) -> dict[str, Any]:
        return await controller.pause(request.expected_state_version)

    @router.post("/control/resume")
    async def resume(request: StateVersionRequest) -> dict[str, Any]:
        return await controller.resume(request.expected_state_version)

    @router.post("/control/stop-after-current")
    async def stop_after_current(request: StateVersionRequest) -> dict[str, Any]:
        return await controller.request_stop_after_current(request.expected_state_version)

    @router.post("/control/retry-feed")
    async def retry_feed(request: OperatorRequest) -> dict[str, Any]:
        return await controller.retry_feed(request.operator, request.expected_state_version)

    @router.post("/control/estop")
    async def estop(request: EstopRequest) -> dict[str, Any]:
        return await controller.software_estop(request.operator)

    @router.post("/manual/enter")
    async def enter_manual(request: OperatorRequest) -> dict[str, Any]:
        return await controller.enter_manual(request.operator, request.expected_state_version)

    @router.post("/maintenance/enter")
    async def enter_maintenance(request: OperatorRequest) -> dict[str, Any]:
        return await controller.enter_maintenance(request.operator, request.expected_state_version)

    @router.post("/control/exit")
    async def exit_control(request: StateVersionRequest) -> dict[str, Any]:
        return await controller.exit_control_mode(request.expected_state_version)

    @router.post("/manual/command")
    @router.post("/maintenance/command")
    async def manual_command(request: ManualCommandRequest) -> dict[str, Any]:
        return await controller.manual_command(request.operator, request.expected_state_version, request.command, request.parameters)

    @router.get("/configuration")
    async def configuration() -> dict[str, Any]:
        return controller.get_configuration()

    @router.post("/configuration/save")
    async def save_configuration(request: ConfigurationSaveRequest) -> dict[str, Any]:
        return await controller.save_configuration(request.operator, request.expected_state_version, request.description, request.values)

    @router.post("/configuration/reset")
    async def reset_configuration(request: ResetConfigurationRequest) -> dict[str, Any]:
        return await controller.reset_configuration(request.operator, request.expected_state_version, request.source)

    @router.get("/history")
    async def history(limit: int = Query(default=100, ge=1, le=1000)) -> dict[str, Any]:
        return await asyncio.to_thread(controller.database.history, limit)

    @router.get("/events")
    async def events(after: int = Query(default=0, ge=0)) -> list[dict[str, Any]]:
        return controller.events.history(after)

    @router.get("/camera/stream")
    async def camera_stream() -> StreamingResponse:
        return StreamingResponse(controller.vision.mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")

    @router.get("/camera/inspection.jpg")
    async def inspection_snapshot() -> Response:
        image = controller.vision.inspection_jpeg()
        if image is None:
            return Response(status_code=404)
        return Response(content=image, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @router.websocket("/ws")
    async def websocket(websocket: WebSocket) -> None:
        await websocket.accept()
        queue = controller.events.subscribe()
        try:
            await websocket.send_json({"sequence": 0, "topic": "state", "payload": controller.snapshot()})
            while True:
                event = await queue.get()
                await websocket.send_json(event)
        except WebSocketDisconnect:
            pass
        finally:
            controller.events.unsubscribe(queue)

    return router
