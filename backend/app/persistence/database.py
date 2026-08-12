from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from ..core.config import PROJECT_ROOT


class Base(DeclarativeBase):
    pass


class SessionRecord(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    operator: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    config_checksum: Mapped[str] = mapped_column(String(64))
    summary_json: Mapped[str] = mapped_column(Text, default="{}")


class FruitCycleRecord(Base):
    __tablename__ = "fruit_cycles"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    fruit_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    yolo_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    detection_json: Mapped[str] = mapped_column(Text, default="{}")
    classification_json: Mapped[str] = mapped_column(Text, default="{}")
    final_condition: Mapped[str | None] = mapped_column(String(48), nullable=True)
    route: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="STARTED")
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SensorSampleRecord(Base):
    __tablename__ = "sensor_samples"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_id: Mapped[str] = mapped_column(ForeignKey("fruit_cycles.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    values_json: Mapped[str] = mapped_column(Text)
    valid: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditEventRecord(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    severity: Mapped[str] = mapped_column(String(16))
    actor: Mapped[str] = mapped_column(String(80))
    topic: Mapped[str] = mapped_column(String(80), index=True)
    session_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    cycle_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")


class ConfigurationVersionRecord(Base):
    __tablename__ = "configuration_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(80), unique=True)
    author: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(240))
    checksum: Mapped[str] = mapped_column(String(64))
    values_json: Mapped[str] = mapped_column(Text)
    activated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))


class Database:
    def __init__(self, data_dir: Path | None = None):
        configured = os.getenv("AFDS_DATA_DIR")
        root = Path(configured) if configured else (data_dir or PROJECT_ROOT / "data")
        if not root.is_absolute():
            root = PROJECT_ROOT / root
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "afds.db"
        self.engine = create_engine(f"sqlite:///{self.path}", connect_args={"check_same_thread": False})
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    def create_session(self, session_id: str, operator: str, config_checksum: str) -> None:
        with self.session_factory.begin() as db:
            db.add(SessionRecord(
                id=session_id,
                operator=operator,
                status="ACTIVE",
                started_at=dt.datetime.now(dt.timezone.utc),
                config_checksum=config_checksum,
            ))

    def finish_session(self, session_id: str, status: str, summary: dict[str, Any]) -> None:
        with self.session_factory.begin() as db:
            row = db.get(SessionRecord, session_id)
            if row:
                row.status = status
                row.ended_at = dt.datetime.now(dt.timezone.utc)
                row.summary_json = json.dumps(summary)

    def create_cycle(self, cycle_id: str, session_id: str, sequence: int) -> None:
        with self.session_factory.begin() as db:
            db.add(FruitCycleRecord(
                id=cycle_id,
                session_id=session_id,
                sequence=sequence,
                started_at=dt.datetime.now(dt.timezone.utc),
            ))

    def update_cycle(self, cycle_id: str, **values: Any) -> None:
        with self.session_factory.begin() as db:
            row = db.get(FruitCycleRecord, cycle_id)
            if not row:
                return
            json_fields = {"detection": "detection_json", "classification": "classification_json"}
            for key, value in values.items():
                target = json_fields.get(key, key)
                if hasattr(row, target):
                    setattr(row, target, json.dumps(value) if target.endswith("_json") else value)

    def save_samples(self, cycle_id: str, samples: list[dict[str, Any]]) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        with self.session_factory.begin() as db:
            db.add_all([
                SensorSampleRecord(
                    cycle_id=cycle_id,
                    sequence=index,
                    timestamp=now,
                    values_json=json.dumps(sample),
                    valid=not bool(sample.get("qualityFlags")),
                )
                for index, sample in enumerate(samples)
            ])

    def audit(self, topic: str, payload: dict[str, Any], actor: str = "system", severity: str = "INFO", session_id: str | None = None, cycle_id: str | None = None) -> None:
        with self.session_factory.begin() as db:
            db.add(AuditEventRecord(
                timestamp=dt.datetime.now(dt.timezone.utc),
                severity=severity,
                actor=actor,
                topic=topic,
                session_id=session_id,
                cycle_id=cycle_id,
                payload_json=json.dumps(payload, default=str),
            ))

    def save_configuration(self, version: str, author: str, description: str, digest: str, values: dict[str, Any]) -> None:
        with self.session_factory.begin() as db:
            db.add(ConfigurationVersionRecord(
                version=version,
                author=author,
                description=description,
                checksum=digest,
                values_json=json.dumps(values),
                activated_at=dt.datetime.now(dt.timezone.utc),
            ))

    def history(self, limit: int = 100) -> dict[str, list[dict[str, Any]]]:
        with self.session_factory() as db:
            sessions = list(db.scalars(select(SessionRecord).order_by(SessionRecord.started_at.desc()).limit(limit)))
            cycles = list(db.scalars(select(FruitCycleRecord).order_by(FruitCycleRecord.started_at.desc()).limit(limit)))
            events = list(db.scalars(select(AuditEventRecord).order_by(AuditEventRecord.timestamp.desc()).limit(limit)))
        return {
            "sessions": [self._session_dict(item) for item in sessions],
            "cycles": [self._cycle_dict(item) for item in cycles],
            "events": [self._event_dict(item) for item in events],
        }

    @staticmethod
    def _session_dict(row: SessionRecord) -> dict[str, Any]:
        return {"id": row.id, "operator": row.operator, "status": row.status, "startedAt": row.started_at.isoformat(), "endedAt": row.ended_at.isoformat() if row.ended_at else None, "summary": json.loads(row.summary_json)}

    @staticmethod
    def _cycle_dict(row: FruitCycleRecord) -> dict[str, Any]:
        return {"id": row.id, "sessionId": row.session_id, "sequence": row.sequence, "fruitType": row.fruit_type, "condition": row.final_condition, "route": row.route, "status": row.status, "startedAt": row.started_at.isoformat(), "completedAt": row.completed_at.isoformat() if row.completed_at else None}

    @staticmethod
    def _event_dict(row: AuditEventRecord) -> dict[str, Any]:
        return {"id": row.id, "timestamp": row.timestamp.isoformat(), "severity": row.severity, "actor": row.actor, "topic": row.topic, "sessionId": row.session_id, "cycleId": row.cycle_id, "payload": json.loads(row.payload_json)}

