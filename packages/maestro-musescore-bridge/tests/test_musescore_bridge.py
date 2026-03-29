from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maestro_musescore_bridge import (  # noqa: E402
    ACTION_KINDS,
    ActionBatch,
    BridgeResponseError,
    BridgeTimeoutError,
    MuseScoreBridgeClient,
)


class FakeBridgeWorker:
    def __init__(self, bridge_dir: Path) -> None:
        self.bridge_dir = bridge_dir
        self.request_path = bridge_dir / "request.json"
        self.response_path = bridge_dir / "response.json"
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.is_set():
            if not self.request_path.exists():
                time.sleep(0.01)
                continue

            request = json.loads(self.request_path.read_text(encoding="utf-8"))
            self.request_path.unlink()

            response = self._handle(request)
            self.response_path.write_text(json.dumps(response, indent=2), encoding="utf-8")

    def _handle(self, request: dict) -> dict:
        request_id = request.get("request_id", "")
        operation = request.get("operation")

        base = {
            "protocol": "maestro.bridge.v1",
            "request_id": request_id,
            "ok": True,
            "result": {},
            "error": "",
        }

        if operation == "ping":
            base["result"] = {"message": "pong", "has_score": True}
            return base

        if operation == "list_actions":
            base["result"] = {"actions": [{"kind": kind} for kind in ACTION_KINDS]}
            return base

        if operation == "score_info":
            base["ok"] = False
            base["error"] = "No score is open"
            return base

        if operation == "apply_actions":
            results = []
            for action in request.get("actions", []):
                if action.get("pitch") == "BAD":
                    results.append({"ok": False, "error": "bad pitch"})
                else:
                    results.append({"ok": True})

            all_ok = all(item.get("ok") is True for item in results)
            fail_on_partial = request.get("fail_on_partial", True)

            base["ok"] = all_ok or (not fail_on_partial)
            if base["ok"] is False:
                base["error"] = "One or more actions failed"
            base["result"] = {
                "command_count": len(results),
                "all_ok": all_ok,
                "results": results,
            }
            return base

        base["ok"] = False
        base["error"] = f"Unknown operation: {operation}"
        return base


class MuseScoreBridgeTests(unittest.TestCase):
    def test_action_batch_helper_methods(self) -> None:
        batch = ActionBatch()
        batch.add_note(pitch="C4", duration="quarter", tick=0, staff=0, voice=0)
        batch.add_dynamic(text="mf", tick=0, staff=0)

        actions = batch.to_list()
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]["kind"], "add_note")
        self.assertEqual(actions[1]["kind"], "add_dynamic")

    def test_client_round_trip_with_fake_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge_dir = Path(tmp)
            worker = FakeBridgeWorker(bridge_dir)
            worker.start()
            try:
                client = MuseScoreBridgeClient(bridge_dir=bridge_dir, timeout=1.0, poll_interval=0.01)

                ping_result = client.ping()
                self.assertEqual(ping_result["message"], "pong")

                apply_result = client.apply_actions(
                    [
                        {"kind": "add_note", "pitch": "C4", "duration": "quarter", "tick": 0},
                        {"kind": "add_dynamic", "text": "mf", "tick": 0},
                    ]
                )
                self.assertEqual(apply_result["command_count"], 2)
                self.assertTrue(apply_result["all_ok"])
            finally:
                worker.stop()

    def test_client_timeout_without_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = MuseScoreBridgeClient(bridge_dir=Path(tmp), timeout=0.2, poll_interval=0.01)
            with self.assertRaises(BridgeTimeoutError):
                client.ping()

    def test_client_raises_on_bridge_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge_dir = Path(tmp)
            worker = FakeBridgeWorker(bridge_dir)
            worker.start()
            try:
                client = MuseScoreBridgeClient(bridge_dir=bridge_dir, timeout=1.0, poll_interval=0.01)
                with self.assertRaises(BridgeResponseError):
                    client.score_info()
            finally:
                worker.stop()


if __name__ == "__main__":
    unittest.main()
