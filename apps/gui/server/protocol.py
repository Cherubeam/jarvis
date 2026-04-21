"""
WebSocket protocol for /ws/chat.

Server → client and client → server event shapes. Mirrored verbatim in
apps/gui/web/src/lib/types.ts (any change here requires a matching change there).

Each event is a plain dict that round-trips cleanly through json.dumps. The
TypedDicts are documentation + lightweight validation; we don't enforce them
at runtime.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

# -- Server → client ---------------------------------------------------------


class SessionMeta(TypedDict):
    id: str
    model: str
    model_short: str
    provider: str
    conversation_path: str
    vault: str | None
    started_at: str
    agents_count: int


class SessionStartEvent(TypedDict):
    type: Literal["session_start"]
    session: SessionMeta


class SystemEvent(TypedDict):
    type: Literal["system"]
    text: str
    time: str


class UserEvent(TypedDict):
    type: Literal["user"]
    id: str
    text: str
    time: str


class ThinkingStartEvent(TypedDict):
    type: Literal["thinking_start"]
    agent: str


class ThinkingEndEvent(TypedDict):
    type: Literal["thinking_end"]
    agent: str


class ChunkEvent(TypedDict):
    type: Literal["chunk"]
    id: str
    agent: str
    delta: str


class StatsBlock(TypedDict, total=False):
    tokens: int
    cost: float
    ttft: int
    total: int


class TextEvent(TypedDict, total=False):
    type: Literal["text"]
    id: str
    agent: str
    markdown: str
    stats: StatsBlock


class ToolResultBlock(TypedDict, total=False):
    summary: str
    preview: str
    path: str


class ToolCallEvent(TypedDict, total=False):
    type: Literal["tool_call"]
    id: str
    agent: str
    tool: str
    args: dict[str, Any]
    result: ToolResultBlock
    elapsed_ms: int
    status: str


class DelegationEvent(TypedDict):
    type: Literal["delegation"]
    id: str
    from_: str  # serialized as "from" — see _rename below
    to: str
    reason: str


class DiffLine(TypedDict):
    kind: Literal["add", "del", "ctx"]
    text: str


class ApprovalPendingEvent(TypedDict, total=False):
    type: Literal["approval_pending"]
    id: str
    tool: str
    agent: str
    path: str
    diff: list[DiffLine]
    summary: str


class ApprovalResolvedEvent(TypedDict):
    type: Literal["approval_resolved"]
    id: str
    approved: bool


class RagMatch(TypedDict):
    date: str
    score: float
    snippet: str
    source: str


class RagResultEvent(TypedDict):
    type: Literal["rag_result"]
    id: str
    query: str
    matches: list[RagMatch]


class ErrorEvent(TypedDict, total=False):
    type: Literal["error"]
    id: str
    message: str


class TotalsEvent(TypedDict):
    type: Literal["totals"]
    messages: int
    tokens: int
    cost: float


class TurnFinishedEvent(TypedDict):
    type: Literal["turn_finished"]
    id: str


# Outbound union — used only as type hint, not enforced.
ServerEvent = (
    SessionStartEvent
    | SystemEvent
    | UserEvent
    | ThinkingStartEvent
    | ThinkingEndEvent
    | ChunkEvent
    | TextEvent
    | ToolCallEvent
    | DelegationEvent
    | ApprovalPendingEvent
    | ApprovalResolvedEvent
    | RagResultEvent
    | ErrorEvent
    | TotalsEvent
    | TurnFinishedEvent
)


# -- Client → server ---------------------------------------------------------


class SubmitMsg(TypedDict):
    type: Literal["submit"]
    text: str


class ApprovalDecisionMsg(TypedDict):
    type: Literal["approval_decision"]
    id: str
    approved: bool


class CancelMsg(TypedDict):
    type: Literal["cancel"]


ClientMsg = SubmitMsg | ApprovalDecisionMsg | CancelMsg


# -- Helpers -----------------------------------------------------------------


def serialize_delegation(ev: DelegationEvent) -> dict[str, Any]:
    """`from` is reserved in JS-friendly JSON; we serialize as 'from' on the wire."""
    out = dict(ev)
    out["from"] = out.pop("from_")
    return out
