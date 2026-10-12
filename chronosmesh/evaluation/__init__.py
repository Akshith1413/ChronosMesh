"""Research evaluation: ChronosMesh vs. arrival-order and wall-clock baselines."""

from chronosmesh.evaluation.metrics import chain_edges, concurrency_scores, mean_ci, prf
from chronosmesh.evaluation.runner import (
    APPROACHES,
    DeliveryMeta,
    EngineRouter,
    run_experiment,
    run_single,
    score_trial,
    stream_through_engines,
    summarize,
)

__all__ = [
    "APPROACHES", "DeliveryMeta", "EngineRouter", "chain_edges", "concurrency_scores", "mean_ci", "prf",
    "run_experiment", "run_single", "score_trial", "stream_through_engines", "summarize",
]
