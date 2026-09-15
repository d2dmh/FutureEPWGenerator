from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime, timezone
import json

VALID_STATES = {"not_started", "ready", "running", "pausing", "paused", "complete", "failed", "warning"}


@dataclass(frozen=True)
class WorkflowStateRecord:
    schema_version: int = 1
    current_stage: str = ""
    state: str = "not_started"
    last_successful_stage: str = ""
    cmip6_complete: int = 0
    cmip6_total: int = 200
    factors_status: str = "not_started"
    generation_status: str = "not_started"
    validation_status: str = "not_started"
    last_error: dict | None = None
    updated_at: str = ""


class WorkflowStateStore:
    """Persistent orchestration state; scientific truth is reconciled from workspace artifacts."""

    def __init__(self, ws):
        self.ws = ws
        self.path = ws.workflow_state_file

    def load(self) -> WorkflowStateRecord:
        if not self.path.is_file():
            return WorkflowStateRecord()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = {f.name for f in fields(WorkflowStateRecord)}
            data = {k: v for k, v in payload.items() if k in allowed}
            record = WorkflowStateRecord(**data)
            if record.state not in VALID_STATES:
                return replace(record, state="not_started")
            return record
        except Exception:
            return WorkflowStateRecord()

    def save(self, record: WorkflowStateRecord) -> None:
        if record.state not in VALID_STATES:
            raise ValueError(f"Unsupported workflow state: {record.state}")
        stamped = replace(record, updated_at=datetime.now(timezone.utc).isoformat())
        payload = asdict(stamped)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def reconcile(self, *, active_process: bool = False) -> WorkflowStateRecord:
        old = self.load()
        snap = self.ws.status_snapshot()
        factors_status = "complete" if self.ws.factors_complete() else "not_started"
        generation_status = "complete" if self.ws.generation_complete() else "not_started"
        validation_outcome = self.ws.validation_outcome()
        validation_status = {
            "not_run": "not_started",
            "pass": "complete",
            "warning": "warning",
            "fail": "failed",
        }[validation_outcome]

        current_stage = old.current_stage
        state = old.state
        last_successful = old.last_successful_stage
        last_error = old.last_error

        if active_process:
            state = "pausing" if old.state == "pausing" else "running"
        elif validation_outcome == "fail":
            state = "failed"
            current_stage = "stage05"
        elif (
            snap.cmip6_total > 0
            and snap.cmip6_complete == snap.cmip6_total
            and factors_status == "complete"
            and generation_status == "complete"
            and validation_status in {"complete", "warning"}
        ):
            state = "warning" if validation_status == "warning" else "complete"
            current_stage = "stage05"
            last_successful = "stage05"
            last_error = None
        elif generation_status == "complete":
            state = "ready"
            current_stage = "stage05"
            last_successful = "stage04"
        elif factors_status == "complete":
            state = "ready"
            current_stage = "stage04"
            last_successful = "stage03"
        elif snap.cmip6_total > 0 and snap.cmip6_complete == snap.cmip6_total:
            state = "ready"
            current_stage = "stage03"
            last_successful = "stage02"
        elif snap.cmip6_complete > 0:
            if old.state == "failed":
                state = "failed"
            else:
                state = "paused"
            current_stage = "stage02"
        elif old.state in {"running", "pausing"} and old.current_stage == "stage02":
            state = "paused"
            current_stage = "stage02"
        elif old.state == "failed":
            state = "failed"
        else:
            state = "ready"
            current_stage = current_stage or "stage02"

        reconciled = replace(
            old,
            current_stage=current_stage,
            state=state,
            last_successful_stage=last_successful,
            cmip6_complete=int(snap.cmip6_complete),
            cmip6_total=int(snap.cmip6_total),
            factors_status=factors_status,
            generation_status=generation_status,
            validation_status=validation_status,
            last_error=last_error,
        )
        self.save(reconciled)
        return self.load()
