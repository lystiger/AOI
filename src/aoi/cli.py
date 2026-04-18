from __future__ import annotations

import argparse
import json
import time
from itertools import count
from pathlib import Path
from urllib import error, request

from aoi.log_manager import LogManager
from aoi.mock_inference import generate_mock_events
from aoi.service import run_server


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

    serve = subparsers.add_parser("serve-http", help="run the AOI ingestion HTTP service")
    serve.add_argument("--host", default="0.0.0.0", help="bind host")
    serve.add_argument("--port", type=int, default=8000, help="bind port")
    serve.add_argument(
        "--output",
        type=Path,
        default=Path("logs/inference.jsonl"),
        help="path to JSONL log file",
    )
    serve.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/aoi.db"),
        help="path to SQLite database file",
    )

    sender = subparsers.add_parser("send-mock-events", help="send mock events to the HTTP service")
    sender.add_argument("--batch-size", type=int, default=5, help="events sent per cycle")
    sender.add_argument("--interval-seconds", type=float, default=5.0, help="delay between cycles")
    sender.add_argument(
        "--endpoint",
        default="http://127.0.0.1:8000/events",
        help="HTTP endpoint for event ingestion",
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
        return

    if args.command == "serve-http":
        run_server(host=args.host, port=args.port, log_path=args.output, db_path=args.db_path)
        return

    if args.command == "send-mock-events":
        for cycle in count(1):
            payload = {"events": [event.to_dict() for event in generate_mock_events(args.batch_size)]}
            body = json.dumps(payload).encode("utf-8")
            http_request = request.Request(
                args.endpoint,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with request.urlopen(http_request, timeout=10) as response:
                    response_body = response.read().decode("utf-8")
            except error.URLError as exc:
                print(f"Cycle {cycle}: failed to send events: {exc}", flush=True)
            else:
                print(
                    f"Cycle {cycle}: sent {args.batch_size} events to {args.endpoint} -> {response_body}",
                    flush=True,
                )
            time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
