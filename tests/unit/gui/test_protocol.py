"""Tests for apps.gui.server.protocol — wire-shape validation."""

import json

from apps.gui.server.protocol import (
    ApprovalPendingEvent,
    ChunkEvent,
    DelegationEvent,
    TextEvent,
    TotalsEvent,
    serialize_delegation,
)


def test_events_round_trip_through_json():
    chunk: ChunkEvent = {"type": "chunk", "id": "u1", "agent": "JARVIS", "delta": "hello"}
    assert json.loads(json.dumps(chunk)) == chunk

    text: TextEvent = {
        "type": "text",
        "id": "u1",
        "agent": "JARVIS",
        "markdown": "**hi**",
        "stats": {"tokens": 42, "cost": 0.0001, "ttft": 100, "total": 200},
    }
    assert json.loads(json.dumps(text)) == text

    approval: ApprovalPendingEvent = {
        "type": "approval_pending",
        "id": "a1",
        "tool": "vault_write",
        "agent": "writer",
        "path": "drafts/x.md",
        "diff": [{"kind": "add", "text": "new"}],
        "summary": "+1 line",
    }
    assert json.loads(json.dumps(approval)) == approval

    totals: TotalsEvent = {"type": "totals", "messages": 3, "tokens": 1234, "cost": 0.0045}
    assert json.loads(json.dumps(totals)) == totals


def test_serialize_delegation_renames_from_field():
    ev: DelegationEvent = {
        "type": "delegation",
        "id": "d1",
        "from_": "JARVIS",
        "to": "writer",
        "reason": "drafting prose",
    }
    out = serialize_delegation(ev)
    assert "from" in out
    assert "from_" not in out
    assert out["from"] == "JARVIS"
    assert out["to"] == "writer"
