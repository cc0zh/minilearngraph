"""Strict, JSON-native B1 request, resource and model-output contracts."""

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError


def _text(value: Any) -> Any:
    if isinstance(value, str):
        if "\x00" in value:
            raise ValueError("Text must not contain NUL.")
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise ValueError("Text must be valid Unicode.") from None
        return value.strip()
    return value


def _timestamp(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    value = _text(value)
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})",
        value,
    ):
        raise ValueError("A timezone-aware RFC3339 timestamp is required.")
    try:
        parsed = datetime.fromisoformat(value.upper())
        # fromisoformat normalizes malformed offsets such as +00:60.
        if value[-1:] not in {"Z", "z"} and (
            int(value[-5:-3]) > 23 or int(value[-2:]) > 59
        ):
            raise ValueError
        return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError):
        raise ValueError("A valid RFC3339 timestamp is required.") from None


Text = Annotated[str, BeforeValidator(_text), StringConstraints(min_length=1)]
Text80 = Annotated[Text, StringConstraints(max_length=80)]
Text100 = Annotated[Text, StringConstraints(max_length=100)]
Text120 = Annotated[Text, StringConstraints(max_length=120)]
Text200 = Annotated[Text, StringConstraints(max_length=200)]
Text500 = Annotated[Text, StringConstraints(max_length=500)]
Text1000 = Annotated[Text, StringConstraints(max_length=1000)]
Text2000 = Annotated[Text, StringConstraints(max_length=2000)]
Text4000 = Annotated[Text, StringConstraints(max_length=4000)]
Text8000 = Annotated[Text, StringConstraints(max_length=8000)]
UUID4Str = Annotated[
    Text,
    StringConstraints(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"),
]
Timestamp = Annotated[Text, BeforeValidator(_timestamp)]
Ref = Annotated[Text80, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")]
QuestionKey = Annotated[Text80, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]
PositiveInt = Annotated[int, Field(ge=1)]
Weight = Annotated[int, Field(ge=1, le=100)]
ActionType = Literal["learn", "practice", "review", "assessment"]
NodeType = Literal["root", "concept", "practice", "assessment"]
Relation = Literal["contains", "prerequisite", "related", "contrast", "application"]
FailureReason = Literal["configuration", "timeout", "transport", "invalid_output", "interrupted"]
GoalField = Literal[
    "title", "intent", "prior_knowledge", "desired_outcome", "time_limit_text",
    "deadline_at", "target_weight", "availability", "preferences",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)


def _unique(values: list[Any]) -> None:
    if len(values) != len(set(values)):
        raise ValueError("Values must be unique.")


def _assumptions(values: Sequence["Assumption"], prefix: str | None = None) -> None:
    _unique([entry.key for entry in values])
    if prefix is not None and any(not entry.key.startswith(prefix) for entry in values):
        raise ValueError("Assumption keys have an invalid source prefix.")


class Availability(StrictModel):
    minutes_per_day: Annotated[int, Field(ge=1, le=1440)]
    days_per_week: Annotated[int, Field(ge=1, le=7)]


class Preferences(StrictModel):
    session_minutes: Annotated[int, Field(ge=1, le=1440)]
    preferred_action_types: Annotated[list[ActionType], Field(max_length=4)]

    @field_validator("preferred_action_types")
    @classmethod
    def unique_actions(cls, values: list[ActionType]) -> list[ActionType]:
        _unique(values)
        return values


class GoalValues(StrictModel):
    title: Text200
    intent: Text100 | None
    prior_knowledge: Text4000 | None
    desired_outcome: Text4000
    time_limit_text: Text1000 | None
    deadline_at: Timestamp | None
    target_weight: Weight
    availability: Availability | None
    preferences: Preferences | None

    @model_validator(mode="after")
    def session_budget(self) -> Self:
        if (
            self.availability and self.preferences
            and self.preferences.session_minutes > self.availability.minutes_per_day
        ):
            raise ValueError("Session length must not exceed the daily budget.")
        return self


class Assumption(StrictModel):
    key: Text120
    field: GoalField | None
    value: Text2000 | None
    reason: Text2000


class SuggestedAssumption(Assumption):
    """Expose the model-only source constraint in the generated JSON Schema."""

    key: Annotated[
        str,
        StringConstraints(min_length=1, max_length=120, pattern=r"^suggested:"),
        BeforeValidator(_text),
    ]


class QuestionOption(StrictModel):
    id: Text80
    label: Text500


class ClarificationQuestion(StrictModel):
    key: QuestionKey
    prompt: Text2000
    options: Annotated[list[QuestionOption], Field(max_length=8)]
    reason: Text2000
    graph_impact: Literal["scope", "nodes", "relations", "teaching", "schedule"]
    allow_custom: bool
    allow_skip: bool
    default_assumption: Text2000 | None

    @model_validator(mode="after")
    def usable_answers(self) -> Self:
        _unique([option.id for option in self.options])
        if not (self.options or self.allow_custom or self.allow_skip):
            raise ValueError("A question must allow at least one answer.")
        if self.allow_skip != (self.default_assumption is not None):
            raise ValueError("Only skippable questions must have a default assumption.")
        return self


class ClarificationAnswer(StrictModel):
    key: Text80
    kind: Literal["choice", "custom", "skip"]
    value: Text4000 | None

    @model_validator(mode="after")
    def answer_value(self) -> Self:
        if (self.kind == "skip") != (self.value is None):
            raise PydanticCustomError("invalid_answer", "Answer kind and value are inconsistent.")
        return self


class Failure(StrictModel):
    code: Text
    message: Text
    reason: FailureReason
    retryable: bool


class CreateGoal(StrictModel):
    prompt: Text8000


class RevisionRequest(StrictModel):
    expected_revision: PositiveInt


class ConfirmedRequest(StrictModel):
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value: Any) -> Any:
        if value is not True:
            raise ValueError("Explicit boolean confirmation is required.")
        return value


class ConfirmGoal(RevisionRequest, ConfirmedRequest):
    values: GoalValues
    answers: Annotated[list[ClarificationAnswer], Field(max_length=8)]
    accepted_suggested_assumption_keys: Annotated[list[Text120], Field(max_length=8)]
    user_assumptions: Annotated[list[Assumption], Field(max_length=16)]

    @field_validator("answers")
    @classmethod
    def unique_answers(cls, answers: list[ClarificationAnswer]) -> list[ClarificationAnswer]:
        if len({answer.key for answer in answers}) != len(answers):
            raise PydanticCustomError("duplicate_question", "Each question must be answered once.")
        return answers

    @model_validator(mode="after")
    def confirmation_lists(self) -> Self:
        _unique(self.accepted_suggested_assumption_keys)
        if any(not key.startswith("suggested:") for key in self.accepted_suggested_assumption_keys):
            raise ValueError("Accepted assumption keys must have suggested source.")
        _assumptions(self.user_assumptions, "user:")
        return self


class ClarificationOutput(StrictModel):
    suggested_values: GoalValues
    questions: Annotated[list[ClarificationQuestion], Field(min_length=1, max_length=8)]
    suggested_assumptions: Annotated[list[SuggestedAssumption], Field(max_length=8)]

    @model_validator(mode="after")
    def clarification_lists(self) -> Self:
        _unique([question.key for question in self.questions])
        _assumptions(self.suggested_assumptions, "suggested:")
        return self


class Position(StrictModel):
    x: Annotated[float, Field(ge=-100000, le=100000, allow_inf_nan=False)]
    y: Annotated[float, Field(ge=-100000, le=100000, allow_inf_nan=False)]


class NodeContent(StrictModel):
    label: Text200
    node_type: NodeType
    description: Text4000
    teaching_strategy: Text4000
    target_weight: Weight


class ModelNode(NodeContent):
    ref: Ref


class NodeInput(ModelNode):
    id: UUID4Str | None
    position: Position | None


class EdgeInput(StrictModel):
    source_ref: Ref
    target_ref: Ref
    relation: Relation


class GraphInput(StrictModel):
    nodes: Annotated[list[NodeInput], Field(min_length=2, max_length=100)]
    edges: Annotated[list[EdgeInput], Field(max_length=500)]


class EditCandidate(GraphInput, RevisionRequest):
    pass


class PublishGraph(RevisionRequest, ConfirmedRequest):
    pass


class ReviseGraph(GraphInput, RevisionRequest, ConfirmedRequest):
    reason: Text2000


class ModelGraph(StrictModel):
    nodes: Annotated[list[ModelNode], Field(min_length=2, max_length=100)]
    edges: Annotated[list[EdgeInput], Field(max_length=500)]

    @model_validator(mode="after")
    def valid_structure(self) -> Self:
        from .validation import validate_graph

        if validate_graph(self.nodes, self.edges):
            raise ValueError("Model graph violates structural constraints.")
        return self


class NodeRead(NodeContent):
    id: UUID4Str
    node_version: PositiveInt
    position: Position | None
    created_at: Timestamp


class EdgeRead(StrictModel):
    source: UUID4Str
    target: UUID4Str
    relation: Relation


class GoalRead(StrictModel):
    id: UUID4Str
    learner_id: Literal["local-user"]
    raw_prompt: Text8000
    status: Literal["draft", "confirmed"]
    revision: PositiveInt
    clarification_status: Literal["generating", "ready", "generation_failed"]
    suggested_values: GoalValues | None
    values: GoalValues | None
    questions: Annotated[list[ClarificationQuestion], Field(max_length=8)]
    answers: Annotated[list[ClarificationAnswer], Field(max_length=8)]
    accepted_suggested_assumption_keys: Annotated[list[Text120], Field(max_length=8)]
    suggested_assumptions: Annotated[list[Assumption], Field(max_length=8)]
    assumptions: Annotated[list[Assumption], Field(max_length=32)]
    clarification_failure: Failure | None
    graph_id: UUID4Str | None
    created_at: Timestamp
    updated_at: Timestamp
    confirmed_at: Timestamp | None

    @model_validator(mode="after")
    def resource_state(self) -> Self:
        _unique([question.key for question in self.questions])
        _unique([answer.key for answer in self.answers])
        _unique(self.accepted_suggested_assumption_keys)
        _assumptions(self.suggested_assumptions, "suggested:")
        _assumptions(self.assumptions)
        if (self.clarification_status == "generation_failed") != (self.clarification_failure is not None):
            raise ValueError("Clarification failure must agree with the resource state.")
        if self.clarification_status == "ready":
            if not self.questions or self.suggested_values is None:
                raise ValueError("Ready clarification requires complete output.")
        elif self.questions or self.suggested_values is not None or self.suggested_assumptions:
            raise ValueError("Unfinished clarification cannot contain partial output.")
        if self.status == "confirmed":
            if self.values is None or self.confirmed_at is None or self.clarification_status != "ready":
                raise ValueError("Confirmed goals require reviewed values and a confirmation time.")
        elif self.values is not None or self.confirmed_at is not None or self.answers or self.accepted_suggested_assumption_keys:
            raise ValueError("Draft goals cannot contain confirmed values or answers.")
        return self


class GraphRead(StrictModel):
    id: UUID4Str
    goal_id: UUID4Str
    status: Literal["generating", "generation_failed", "candidate", "published"]
    revision: PositiveInt
    nodes: Annotated[list[NodeRead], Field(max_length=100)]
    edges: Annotated[list[EdgeRead], Field(max_length=500)]
    generation_failure: Failure | None
    created_at: Timestamp
    updated_at: Timestamp
    published_at: Timestamp | None
    last_revision_reason: Text2000 | None

    @model_validator(mode="after")
    def resource_state(self) -> Self:
        from .validation import validate_graph

        if (self.status == "generation_failed") != (self.generation_failure is not None):
            raise ValueError("Generation failure must agree with the resource state.")
        if self.status in {"generating", "generation_failed"}:
            if self.nodes or self.edges:
                raise ValueError("Unfinished graphs cannot contain partial output.")
        elif validate_graph(self.nodes, self.edges, scope="graph"):
            raise ValueError("Stored graph violates structural constraints.")
        if (self.status == "published") != (self.published_at is not None):
            raise ValueError("Publication time must agree with the resource state.")
        return self


class GraphWriteResult(StrictModel):
    graph: GraphRead
    ref_map: dict[Ref, UUID4Str]


class GoalList(StrictModel):
    items: list[GoalRead]


class GraphList(StrictModel):
    items: list[GraphRead]


class Issue(StrictModel):
    path: list[Text | int]
    code: Text
    message: Text
    node_ids: list[Text]
    edge_indexes: list[Annotated[int, Field(ge=0)]]


class ErrorDetails(StrictModel):
    resource_type: Literal["goal", "graph"] | None
    resource_id: UUID4Str | None
    expected_revision: PositiveInt | None
    current_revision: PositiveInt | None
    failure_reason: FailureReason | None
    issues: list[Issue]


class ApiError(StrictModel):
    code: Text
    message: Text
    details: ErrorDetails
    retryable: bool
