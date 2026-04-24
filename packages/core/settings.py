"""Typed configuration for JARVIS.

Replaces dict-based ``load_config`` with a ``pydantic-settings`` model.
Loaded from ``config/default.yaml`` deep-merged with ``config/local.yaml``.
See ADR-032 in ``docs/product/decisions.md``.
"""
