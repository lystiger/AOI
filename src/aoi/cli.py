from __future__ import annotations

import argparse
from pathlib import Path

from aoi.log_manager import LogManager
from aoi.mock_inference import generate_mock_events


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AOI logging pipeline utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate-mock-logs", help="write mock inference logs")
    generate.add_argument("--count", type=int, default=10, help="number of mock events")
    generate.add_argument(
        "--output",
        type=Path,
        default=Path("logs/inference.jsonl"),
        help="path to JSONL log file",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "generate-mock-logs":
        manager = LogManager(args.output)
        for event in generate_mock_events(args.count):
            manager.write_json(event)
        print(f"Wrote {args.count} events to {args.output}")


if __name__ == "__main__":
    main()

