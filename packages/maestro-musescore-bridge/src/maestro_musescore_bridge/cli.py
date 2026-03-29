from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .client import BridgeError, MuseScoreBridgeClient


def _load_actions_from_file(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(payload, list):
        return [dict(item) for item in payload]

    if isinstance(payload, dict):
        if "actions" in payload and isinstance(payload["actions"], list):
            return [dict(item) for item in payload["actions"]]

    raise ValueError("JSON file must be an array of actions or an object with an 'actions' array")


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="maestro-musescore-bridge",
        description="Control MuseScore by sending actions to the Maestro Python Bridge plugin.",
    )
    parser.add_argument(
        "--bridge-dir",
        type=Path,
        default=None,
        help="Bridge directory used by request.json/response.json (default: ~/.maestro-musescore-bridge)",
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--poll-interval", type=float, default=0.05)

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("ping")
    subparsers.add_parser("list-actions")
    subparsers.add_parser("score-info")
    subparsers.add_parser("read-score")

    apply_parser = subparsers.add_parser("apply-json")
    apply_parser.add_argument("path", type=Path)
    apply_parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Return success even when one or more actions fail on the plugin side.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _make_parser()
    args = parser.parse_args(argv)

    try:
        client = MuseScoreBridgeClient(
            bridge_dir=args.bridge_dir,
            timeout=args.timeout,
            poll_interval=args.poll_interval,
        )

        if args.command == "ping":
            result = client.ping()
        elif args.command == "list-actions":
            result = client.list_actions()
        elif args.command == "score-info":
            result = client.score_info()
        elif args.command == "read-score":
            result = client.read_score()
        elif args.command == "apply-json":
            actions = _load_actions_from_file(args.path)
            result = client.apply_actions(actions, fail_on_partial=not args.allow_partial)
        else:
            parser.error(f"Unknown command: {args.command}")
            return 2
    except BridgeError as exc:
        parser.exit(1, f"{type(exc).__name__}: {exc}\n")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, f"{type(exc).__name__}: {exc}\n")

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
