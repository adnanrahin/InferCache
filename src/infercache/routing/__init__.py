"""Routing package."""

from infercache.routing.cascade import CascadeStage, ModelCascade, default_escalate

__all__ = ["CascadeStage", "ModelCascade", "default_escalate"]
