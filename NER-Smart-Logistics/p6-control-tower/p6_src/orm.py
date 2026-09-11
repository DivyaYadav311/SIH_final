"""SQLAlchemy tables owned by P6: incidents, alerts, simulation_results."""
from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IncidentRow(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    reported_by: Mapped[str] = mapped_column(String(128))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    incident_type: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[str] = mapped_column(String(40))
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="UNDER_VERIFICATION")
    detected_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    verification_backend: Mapped[str | None] = mapped_column(String(32), nullable=True)
    exif_gps_mismatch: Mapped[bool] = mapped_column(Boolean, default=False)
    exif_distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    road_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    district_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AlertRow(Base):
    __tablename__ = "alerts"

    alert_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(256))
    affected_road: Mapped[str | None] = mapped_column(String(64), nullable=True)
    affected_shipments: Mapped[int] = mapped_column(Integer, default=0)
    affected_districts_json: Mapped[str] = mapped_column(Text, default="[]")
    recommended_action: Mapped[str] = mapped_column(String(64))
    generated_at: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(32), default="P6_ENGINE")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")


class SimulationRow(Base):
    __tablename__ = "simulation_results"

    scenario_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scenario_type: Mapped[str] = mapped_column(String(64))
    road_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_json: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[str] = mapped_column(String(40))
