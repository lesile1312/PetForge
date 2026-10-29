from __future__ import annotations

import json
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from .corpus import EvalResult


_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
_SAFE_CASE_ID = re.compile(r"case_[a-f0-9]{8,32}\Z")
_SAFE_ERROR_CODE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_STAGES = {
    "preflight",
    "detection",
    "candidate_pose",
    "cutout",
    "generation",
    "layer_segmentation",
    "review",
    "idle",
    "run_left",
    "run_right",
    "wave",
    "phone_crouch",
}
_OUTCOMES = {"passed", "failed", "skipped", "rejected", "needs_review"}


def _metric(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _serialize_result(result: EvalResult) -> dict[str, object]:
    if not isinstance(result.case_id, str) or _SAFE_CASE_ID.fullmatch(result.case_id) is None:
        raise ValueError("invalid_case_id")
    if (
        not isinstance(result.model_id, str)
        or _SAFE_ID.fullmatch(result.model_id) is None
        or not isinstance(result.device_id, str)
        or _SAFE_ID.fullmatch(result.device_id) is None
    ):
        raise ValueError("invalid_model_or_device_id")
    if not all(
        _metric(value)
        for value in (result.elapsed_ms, result.peak_memory_bytes, result.correction_count)
    ):
        raise ValueError("invalid_report_metric")
    if not isinstance(result.stages, dict):
        raise ValueError("invalid_stages")
    for stage, outcome in result.stages.items():
        if not isinstance(stage, str) or stage not in _STAGES:
            raise ValueError("invalid_stage_outcome")
        if not isinstance(outcome, str) or outcome not in _OUTCOMES:
            raise ValueError("invalid_stage_outcome")
    if result.stage_elapsed_ms is not None:
        if not isinstance(result.stage_elapsed_ms, dict):
            raise ValueError("invalid_stage_timing")
        for stage, elapsed_ms in result.stage_elapsed_ms.items():
            if not isinstance(stage, str) or stage not in _STAGES or not _metric(elapsed_ms):
                raise ValueError("invalid_stage_timing")
    if result.peak_gpu_memory_bytes is not None and not _metric(result.peak_gpu_memory_bytes):
        raise ValueError("invalid_report_metric")
    if result.error_code is not None and (
        not isinstance(result.error_code, str)
        or _SAFE_ERROR_CODE.fullmatch(result.error_code) is None
    ):
        raise ValueError("invalid_error_code")

    serialized: dict[str, object] = {
        "case_id": result.case_id,
        "model_id": result.model_id,
        "device_id": result.device_id,
        "elapsed_ms": result.elapsed_ms,
        "peak_memory_bytes": result.peak_memory_bytes,
        "correction_count": result.correction_count,
        "stages": dict(sorted(result.stages.items())),
        "error_code": result.error_code,
    }
    if result.stage_elapsed_ms is not None:
        serialized["stage_elapsed_ms"] = dict(sorted(result.stage_elapsed_ms.items()))
    if result.peak_gpu_memory_bytes is not None:
        serialized["peak_gpu_memory_bytes"] = result.peak_gpu_memory_bytes
    return serialized


def write_eval_report(results: list[EvalResult], output_path: Path) -> Path:
    """Write an allowlisted, atomic JSON report with no source or prompt fields."""
    if not isinstance(results, list) or any(not isinstance(item, EvalResult) for item in results):
        raise ValueError("invalid_report_results")
    document = {
        "schema_version": 1,
        "results": [_serialize_result(result) for result in results],
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
            delete=False,
        ) as stream:
            temporary_name = stream.name
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary_name, output)
    except OSError as error:
        if temporary_name is not None:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass
        raise OSError("report_write_failed") from error
    return output
