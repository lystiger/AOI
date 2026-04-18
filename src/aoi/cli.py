from __future__ import annotations

import argparse
import time
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

    stream = subparsers.add_parser("stream-mock-logs", help="continuously write mock inference logs")
    stream.add_argument("--batch-size", type=int, default=5, help="events written per cycle")
    stream.add_argument("--interval-seconds", type=float, default=5.0, help="delay between cycles")
    stream.add_argument(
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
        return

    if args.command == "stream-mock-logs":
        manager = LogManager(args.output)
        cycle = 0
        while True:
            cycle += 1
            for event in generate_mock_events(args.batch_size):
                manager.write_json(event)
            print(
                f"Cycle {cycle}: wrote {args.batch_size} events to {args.output}",
                flush=True,
            )
            time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
