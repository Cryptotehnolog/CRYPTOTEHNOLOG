"""
Read-only cutover export/report bundle over compact review digest.

Модуль intentionally ограничен reporting/export semantics без durable storage,
workflow engine, action semantics или real cutover execution.
"""

from __future__ import annotations

from dataclasses import dataclass

from .bybit_trade_count_cutover_review_compact_digest import (
    BybitTradeCountCutoverReviewCompactDigest,
)


@dataclass(slots=True, frozen=True)
class BybitTradeCountCutoverExportReportBundle:
    """Structured read-only export/report bundle for current cutover review state."""

    contour: str
    scope_mode: str
    headline: str
    discussion_state: str
    manual_review_state: str
    cutover_evaluation_state: str
    cutover_readiness_state: str
    compared_symbols: int
    ready_symbols: int
    not_ready_symbols: int
    blocked_symbols: int
    reasons_summary: tuple[str, ...]
    compact_symbol_exceptions: tuple[str, ...]
    export_text_summary: str
    current_compact_digest: BybitTradeCountCutoverReviewCompactDigest


def build_cutover_export_report_bundle(
    *,
    compact_digest: BybitTradeCountCutoverReviewCompactDigest,
) -> BybitTradeCountCutoverExportReportBundle:
    export_text_summary = (
        f"{compact_digest.headline} "
        f"[discussion={compact_digest.discussion_state}; "
        f"manual_review={compact_digest.manual_review_state}; "
        f"evaluation={compact_digest.cutover_evaluation_state}; "
        f"readiness={compact_digest.cutover_readiness_state}; "
        f"compared={compact_digest.compared_symbols}; "
        f"ready={compact_digest.ready_symbols}; "
        f"not_ready={compact_digest.not_ready_symbols}; "
        f"blocked={compact_digest.blocked_symbols}]"
    )
    return BybitTradeCountCutoverExportReportBundle(
        contour=compact_digest.contour,
        scope_mode=compact_digest.scope_mode,
        headline=compact_digest.headline,
        discussion_state=compact_digest.discussion_state,
        manual_review_state=compact_digest.manual_review_state,
        cutover_evaluation_state=compact_digest.cutover_evaluation_state,
        cutover_readiness_state=compact_digest.cutover_readiness_state,
        compared_symbols=compact_digest.compared_symbols,
        ready_symbols=compact_digest.ready_symbols,
        not_ready_symbols=compact_digest.not_ready_symbols,
        blocked_symbols=compact_digest.blocked_symbols,
        reasons_summary=compact_digest.reasons_summary,
        compact_symbol_exceptions=compact_digest.compact_symbol_exceptions,
        export_text_summary=export_text_summary,
        current_compact_digest=compact_digest,
    )
