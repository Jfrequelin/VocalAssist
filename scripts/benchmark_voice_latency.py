#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure project root is importable when running as a script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.assistant.voice_slo import (
    VoiceLatencySample,
    compute_latency_summary,
    validate_e2e_latency_slo,
)


def _load_samples_from_json(path: Path) -> list[VoiceLatencySample]:
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Le fichier JSON doit contenir une liste de samples")

    samples: list[VoiceLatencySample] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Sample {idx} invalide: objet attendu")

        try:
            sample = VoiceLatencySample(
                stt_ms=float(item["stt_ms"]),
                orchestrator_ms=float(item["orchestrator_ms"]),
                tts_ms=float(item["tts_ms"]),
                network_ms=float(item.get("network_ms", 0.0)),
            )
        except KeyError as exc:
            raise ValueError(f"Sample {idx} incomplet: champ manquant {exc}") from exc

        samples.append(sample)

    return samples


def _generate_mock_samples(sample_count: int, seed: int) -> list[VoiceLatencySample]:
    if sample_count <= 0:
        raise ValueError("sample_count doit etre > 0")

    rng = random.Random(seed)
    samples: list[VoiceLatencySample] = []
    for _ in range(sample_count):
        # Distribution moderee representative d'un pipeline local stable.
        stt_ms = rng.uniform(320.0, 520.0)
        orchestrator_ms = rng.uniform(70.0, 180.0)
        tts_ms = rng.uniform(380.0, 620.0)
        network_ms = rng.uniform(90.0, 260.0)
        samples.append(
            VoiceLatencySample(
                stt_ms=stt_ms,
                orchestrator_ms=orchestrator_ms,
                tts_ms=tts_ms,
                network_ms=network_ms,
            )
        )

    return samples


def _render_markdown_report(
    *,
    summary: dict[str, float],
    threshold_ms: float,
    sample_origin: str,
    samples: list[VoiceLatencySample],
) -> str:
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    slo_ok = summary["median_e2e_ms"] <= threshold_ms
    verdict = "PASS" if slo_ok else "FAIL"

    top_samples = sorted(samples, key=lambda s: s.e2e_ms, reverse=True)[:5]

    lines = [
        "# Voice Latency Benchmark Report",
        "",
        f"Generated at: {now}",
        f"Sample source: {sample_origin}",
        "",
        "## SLO",
        "",
        f"- Target median E2E <= {threshold_ms:.1f} ms",
        f"- Observed median E2E: {summary['median_e2e_ms']:.2f} ms",
        f"- Verdict: {verdict}",
        "",
        "## Summary",
        "",
        f"- Sample count: {int(summary['sample_count'])}",
        f"- Median E2E: {summary['median_e2e_ms']:.2f} ms",
        f"- P95 E2E: {summary['p95_e2e_ms']:.2f} ms",
        f"- Max E2E: {summary['max_e2e_ms']:.2f} ms",
        "",
        "## Top 5 Slowest Samples",
        "",
        "| Rank | STT ms | Orchestrator ms | TTS ms | Network ms | E2E ms |",
        "|---:|---:|---:|---:|---:|---:|",
    ]

    for idx, sample in enumerate(top_samples, start=1):
        lines.append(
            "| "
            f"{idx} | {sample.stt_ms:.2f} | {sample.orchestrator_ms:.2f} | "
            f"{sample.tts_ms:.2f} | {sample.network_ms:.2f} | {sample.e2e_ms:.2f} |"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark latence E2E et validation SLO pour pipeline vocal"
    )
    parser.add_argument(
        "--input-json",
        type=Path,
        default=None,
        help="Chemin vers un JSON de samples (liste de {stt_ms, orchestrator_ms, tts_ms, network_ms})",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=60,
        help="Nombre de samples synthetiques si --input-json est absent",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=302,
        help="Seed pour generation reproductible",
    )
    parser.add_argument(
        "--max-median-ms",
        type=float,
        default=1800.0,
        help="Seuil SLO de mediane E2E en ms",
    )
    parser.add_argument(
        "--report-file",
        type=Path,
        default=Path("docs/03-delivery/voice-latency-benchmark-latest.md"),
        help="Chemin du rapport markdown a ecrire",
    )
    parser.add_argument(
        "--samples-out",
        type=Path,
        default=Path("data/voice_latency_samples.latest.json"),
        help="Chemin de sortie pour archiver les samples utilises",
    )

    args = parser.parse_args()

    if args.input_json is not None:
        samples = _load_samples_from_json(args.input_json)
        sample_origin = str(args.input_json)
    else:
        samples = _generate_mock_samples(args.sample_count, args.seed)
        sample_origin = f"generated(seed={args.seed}, count={args.sample_count})"

    summary = compute_latency_summary(samples)
    slo_ok = validate_e2e_latency_slo(samples, max_median_ms=args.max_median_ms)

    args.samples_out.parent.mkdir(parents=True, exist_ok=True)
    args.samples_out.write_text(
        json.dumps([asdict(sample) for sample in samples], indent=2),
        encoding="utf-8",
    )

    report = _render_markdown_report(
        summary=summary,
        threshold_ms=args.max_median_ms,
        sample_origin=sample_origin,
        samples=samples,
    )
    args.report_file.parent.mkdir(parents=True, exist_ok=True)
    args.report_file.write_text(report, encoding="utf-8")

    print(f"report_file={args.report_file}")
    print(f"samples_file={args.samples_out}")
    print(f"sample_count={int(summary['sample_count'])}")
    print(f"median_e2e_ms={summary['median_e2e_ms']:.2f}")
    print(f"p95_e2e_ms={summary['p95_e2e_ms']:.2f}")
    print(f"max_e2e_ms={summary['max_e2e_ms']:.2f}")
    print(f"slo_target_ms={args.max_median_ms:.2f}")
    print(f"slo_verdict={'PASS' if slo_ok else 'FAIL'}")

    return 0 if slo_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
