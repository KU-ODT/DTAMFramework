"""Schema definitions for dashboard modules, metrics, and actions."""

from pydantic import BaseModel, Field


class ModuleCard(BaseModel):
    slug: str = Field(..., description="Unique module key used by backend and frontend.")
    title: str
    subtitle: str
    description: str
    icon: str
    accent: str
    endpoint: str


class MetricItem(BaseModel):
    label: str
    value: str
    hint: str


class ActionItem(BaseModel):
    id: str
    label: str
    description: str


class ModuleOverview(BaseModel):
    slug: str
    headline: str
    summary: str
    status: str
    metrics: list[MetricItem]
    actions: list[ActionItem]
