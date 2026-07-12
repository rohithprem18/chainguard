"""Pydantic request/response models for the ChainGuard API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ADDRESS_PATTERN = r"^0x[a-fA-F0-9]{40}$"


class ScoreRequest(BaseModel):
    address: str = Field(..., description="An Ethereum address, 0x followed by 40 hex characters.")


class Reason(BaseModel):
    fact: str
    weight: float
    direction: Literal["raises", "lowers"]


class Activity(BaseModel):
    sent: int
    received: int
    unique_counterparties: int
    lifetime_days: int


class ScoreResponse(BaseModel):
    address: str
    risk_score: float
    risk_band: Literal["low", "medium", "high"]
    top_reasons: list[Reason]
    activity: Activity
    disclaimer: str


class ExampleAddress(BaseModel):
    address: str


class ModelInfoResponse(BaseModel):
    trained_on: str
    n_rows: int
    n_train: int
    n_test: int
    positive_rate: float
    cv_pr_auc_mean: float
    cv_pr_auc_std: float
    baseline_logreg_pr_auc: float
    pr_auc: float
    roc_auc: float
    precision_at_100: float
    recall_at_90_precision: float
    brier_before_calibration: float
    brier_after_calibration: float
    confusion_matrix: dict
    thresholds: dict[str, float]


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    message: str
    hint: str
