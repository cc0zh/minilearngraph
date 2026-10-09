"""The twelve B1 routes and their uniform, input-safe error contract."""

import re
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi import Path as ApiPath
from fastapi.exceptions import RequestValidationError
from pydantic import BeforeValidator
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from mini_learngraph.api.security import (
    SecurityBoundary,
    error_body,
    issue,
    storage_busy,
)
from mini_learngraph.api.settings import ServerSettings
from mini_learngraph.learning.errors import DomainError
from mini_learngraph.learning.generation import Generator
from mini_learngraph.learning.schemas import (
    ApiError,
    ConfirmGoal,
    CreateGoal,
    EditCandidate,
    GoalList,
    GoalRead,
    GraphList,
    GraphRead,
    GraphWriteResult,
    PublishGraph,
    ReviseGraph,
    RevisionRequest,
)
from mini_learngraph.learning.service import LearningService
from mini_learngraph.learning.storage import Store

UUID4_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
ResourceId = Annotated[str, ApiPath(pattern=UUID4_PATTERN, min_length=36, max_length=36)]
GoalStatus = Literal["draft", "confirmed"]
GraphStatus = Literal["generating", "generation_failed", "candidate", "published"]


def _query_revision(value: Any) -> Any:
    if value is None:
        return value
    if not isinstance(value, str) or re.fullmatch(r"[0-9]+", value) is None:
        raise ValueError("Revision must be a positive integer.")
    return int(value)


QueryRevision = Annotated[int | None, BeforeValidator(_query_revision), Query(ge=1)]
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ApiError, "description": description}
    for status, description in {
        400: "Invalid strict JSON",
        403: "Local host or origin rejected",
        404: "Resource or route not found",
        405: "Method not allowed",
        409: "Revision or state conflict",
        413: "Body exceeds 512 KiB",
        415: "JSON media type required",
        422: "Request or graph validation failed",
        500: "Safe internal error",
        502: "Model generation failed",
        503: "Model configuration missing or storage busy",
        504: "Model generation timed out",
    }.items()
}


def _validation_issues(exc: RequestValidationError) -> list[dict[str, Any]]:
    issues = []
    for entry in exc.errors():
        kind = entry["type"]
        if kind == "missing":
            code, message = "required", "A required field is missing."
        elif kind == "extra_forbidden":
            code, message = "extra", "Unexpected fields are not allowed."
        elif kind == "duplicate_question":
            code, message = "duplicate_question", "Each question must be answered once."
        elif kind == "invalid_answer":
            code, message = "invalid_answer", "Answer kind and value are inconsistent."
        elif kind.endswith(("_type", "_parsing")):
            code, message = "type", "Field has an invalid type."
        else:
            code, message = "constraint", "Field does not meet its constraints."
        location = list(entry.get("loc", ("body",)))
        # Unknown property names may themselves contain private input. Schema
        # validator messages and ctx also may include entire rejected values.
        if code == "extra":
            location = location[:-1]
        issues.append(issue(location, code, message))
    return issues


def _queries(allowed: frozenset[str]):
    async def check(request: Request) -> None:
        keys = [key for key, _ in request.query_params.multi_items()]
        if any(key not in allowed for key in keys) or len(set(keys)) != len(keys):
            raise HTTPException(422)
    return Depends(check)


def create_app(
    db_path: Path | str | None = None, generator: Generator | None = None
) -> FastAPI:
    settings = ServerSettings()
    store = Store(Path(db_path) if db_path is not None else settings.db_path)
    service = LearningService(store, generator)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        def initialize() -> None:
            store.initialize()
            store.recover_interrupted()
        await run_in_threadpool(initialize)
        yield

    app = FastAPI(
        title="mini-learngraph B1", version="1.0.0", lifespan=lifespan,
        redirect_slashes=False,
    )
    app.state.store = store
    app.state.service = service
    app.state.server_settings = settings
    app.add_middleware(SecurityBoundary, allowed_origins=settings.allowed_origins)

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(exc.as_dict(), exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(error_body(
            "validation_failed", "Request validation failed.", issues=_validation_issues(exc)
        ), 422)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        codes = {
            404: ("route_not_found", "Route was not found."),
            405: ("method_not_allowed", "Method is not allowed."),
            422: ("validation_failed", "Unknown or duplicate query parameters."),
        }
        code, message = codes.get(exc.status_code, ("internal_error", "Request failed."))
        details = [issue(["query"], "extra", message)] if exc.status_code == 422 else []
        # Only the standard Allow header is safe; never forward arbitrary headers
        # or detail values attached to an exception by application code.
        headers = {"Allow": exc.headers["Allow"]} if exc.headers and "Allow" in exc.headers else None
        return JSONResponse(error_body(code, message, issues=details), exc.status_code, headers)

    @app.exception_handler(Exception)
    async def internal_error(_: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, sqlite3.Error) and storage_busy(exc):
            return JSONResponse(error_body(
                "storage_busy", "Storage is temporarily busy.", retryable=True
            ), 503)
        return JSONResponse(error_body("internal_error", "An internal error occurred."), 500)

    router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)
    no_query = [_queries(frozenset())]

    @router.get("/goals", response_model=GoalList, dependencies=[_queries(frozenset({"status"}))])
    async def list_goals(status: GoalStatus | None = None) -> dict[str, Any]:
        return {"items": await run_in_threadpool(store.list_goals, status=status)}

    @router.post("/goals", response_model=GoalRead, status_code=201, dependencies=no_query)
    async def create_goal(body: CreateGoal) -> dict[str, Any]:
        return await service.create_goal(body)

    @router.get("/goals/{goal_id}", response_model=GoalRead, dependencies=no_query)
    async def get_goal(goal_id: ResourceId) -> dict[str, Any]:
        return await run_in_threadpool(store.get_goal, goal_id)

    @router.post("/goals/{goal_id}/clarify", response_model=GoalRead, dependencies=no_query)
    async def retry_clarify(goal_id: ResourceId, body: RevisionRequest) -> dict[str, Any]:
        return await service.retry_clarify(goal_id, body)

    @router.post("/goals/{goal_id}/confirm", response_model=GoalRead, dependencies=no_query)
    async def confirm_goal(goal_id: ResourceId, body: ConfirmGoal) -> dict[str, Any]:
        return await service.confirm_goal(goal_id, body)

    @router.get("/graphs", response_model=GraphList,
                dependencies=[_queries(frozenset({"goal_id", "status"}))])
    async def list_graphs(
        goal_id: Annotated[str | None, Query(pattern=UUID4_PATTERN, min_length=36, max_length=36)] = None,
        status: GraphStatus | None = None,
    ) -> dict[str, Any]:
        return {"items": await run_in_threadpool(store.list_graphs, goal_id=goal_id, status=status)}

    @router.post("/goals/{goal_id}/graphs", response_model=GraphRead,
                 status_code=201, dependencies=no_query)
    async def create_graph(goal_id: ResourceId, body: RevisionRequest) -> dict[str, Any]:
        return await service.create_graph(goal_id, body)

    @router.get("/graphs/{graph_id}", response_model=GraphRead,
                dependencies=[_queries(frozenset({"revision"}))])
    async def get_graph(
        graph_id: ResourceId,
        revision: QueryRevision = None,
    ) -> dict[str, Any]:
        return await run_in_threadpool(
            store.get_graph, graph_id, revision=revision
        )

    @router.post("/graphs/{graph_id}/generate", response_model=GraphRead, dependencies=no_query)
    async def retry_graph(graph_id: ResourceId, body: RevisionRequest) -> dict[str, Any]:
        return await service.retry_graph(graph_id, body)

    @router.put("/graphs/{graph_id}", response_model=GraphWriteResult, dependencies=no_query)
    async def edit_graph(graph_id: ResourceId, body: EditCandidate) -> dict[str, Any]:
        return await service.edit_graph(graph_id, body)

    @router.post("/graphs/{graph_id}/publish", response_model=GraphRead, dependencies=no_query)
    async def publish_graph(graph_id: ResourceId, body: PublishGraph) -> dict[str, Any]:
        return await service.publish_graph(graph_id, body)

    @router.post("/graphs/{graph_id}/revise", response_model=GraphWriteResult, dependencies=no_query)
    async def revise_graph(graph_id: ResourceId, body: ReviseGraph) -> dict[str, Any]:
        return await service.revise_graph(graph_id, body)

    app.include_router(router)
    return app
