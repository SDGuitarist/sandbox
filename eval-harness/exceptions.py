"""Custom exceptions for the spec eval gate."""

from __future__ import annotations


class SpecEvalError(Exception):
    """Base exception for spec eval gate."""


class ExtractionError(SpecEvalError):
    """Failed to extract claims from spec."""


class ScoringError(SpecEvalError):
    """Failed to score a claim against generated code."""
