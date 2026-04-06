from __future__ import annotations

import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import scrolledtext

# Allow running this script directly without installation.
TESTING_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTING_DIR.parent
SRC_DIR = PACKAGE_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from maestro_musescore_bridge import BridgeError, MuseScoreBridgeClient


class BridgeTesterUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Maestro Bridge - Lightweight Tester")
        self.root.geometry("760x520")

        self.client = MuseScoreBridgeClient(timeout=8.0, poll_interval=0.05)
        self.progress_path = TESTING_DIR / "last_action_attempt.json"

        frame = tk.Frame(root)
        frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(frame, text="Ping", width=14, command=self.on_ping).pack(side=tk.LEFT, padx=4)
        tk.Button(frame, text="Score Info", width=14, command=self.on_score_info).pack(side=tk.LEFT, padx=4)
        tk.Button(frame, text="Seed Basics", width=14, command=self.on_seed_basics).pack(side=tk.LEFT, padx=4)
        tk.Button(frame, text="Add Markings", width=14, command=self.on_add_markings).pack(side=tk.LEFT, padx=4)
        tk.Button(frame, text="All Features", width=14, command=self.on_all_features).pack(side=tk.LEFT, padx=4)

        frame2 = tk.Frame(root)
        frame2.pack(fill=tk.X, padx=10)

        tk.Button(frame2, text="Read Score", width=14, command=self.on_read_score).pack(side=tk.LEFT, padx=4, pady=(0, 8))
        tk.Button(frame2, text="Clear Log", width=14, command=self.clear_log).pack(side=tk.LEFT, padx=4, pady=(0, 8))

        self.log_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Menlo", 11))
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.log("Bridge tester ready.")
        self.log("1) In MuseScore open Plugins > Maestro > Maestro Plugin and keep it open.")
        self.log("2) Use buttons below to send live score edits.")
        self.log(f"3) If a crash happens during All Features, inspect: {self.progress_path}")

    def log(self, message: str) -> None:
        self.log_box.insert(tk.END, message + "\n")
        self.log_box.see(tk.END)

    def clear_log(self) -> None:
        self.log_box.delete("1.0", tk.END)

    def run(self, label: str, fn) -> None:
        self.log(f"\n=== {label} ===")
        try:
            result = fn()
            self.log(json.dumps(result, indent=2, sort_keys=True))
        except BridgeError as exc:
            self.log(f"BridgeError: {exc}")
        except Exception as exc:  # noqa: BLE001
            self.log(f"Unexpected error: {type(exc).__name__}: {exc}")

    def on_ping(self) -> None:
        self.run("PING", self.client.ping)

    def on_score_info(self) -> None:
        self.run("SCORE INFO", self.client.score_info)

    def on_read_score(self) -> None:
        self.run("READ SCORE", self.client.read_score)

    def on_seed_basics(self) -> None:
        def _do():
            batch = self.client.batch()
            batch.append_measures(count=4)
            batch.add_time_signature(numerator=4, denominator=4, tick=0, staff=0)
            batch.add_key_signature(key="C", tick=0, staff=0)
            batch.add_tempo(bpm=96, text="Andante", tick=0, staff=0)
            batch.add_note(pitch="C4", duration="quarter", tick=0, staff=0, voice=0)
            batch.add_note(pitch="D4", duration="quarter", tick=480, staff=0, voice=0)
            batch.add_note(pitch="E4", duration="quarter", tick=960, staff=0, voice=0)
            batch.add_note(pitch="F4", duration="quarter", tick=1440, staff=0, voice=0)
            return self.client.apply_batch(batch)

        self.run("SEED BASICS", _do)

    def on_add_markings(self) -> None:
        def _do():
            batch = self.client.batch()
            batch.add_dynamic(text="mf", tick=0, staff=0)
            batch.add_staff_text(text="dolce", tick=0, staff=0)
            batch.add_rehearsal_mark(text="A", tick=0, staff=0)
            batch.add_expression_text(text="espressivo", tick=480, staff=0)
            batch.add_lyrics(text="la", tick=0, staff=0, voice=0, verse=0)
            batch.write_lyrics(syllables=["la", "la", "la", "la"], tick=0, staff=0, voice=0, verse=1)
            return self.client.apply_batch(batch, fail_on_partial=False)

        self.run("ADD MARKINGS", _do)

    def _all_feature_actions(self) -> list[tuple[str, dict]]:
        return [
            ("append_measures", {"kind": "append_measures", "count": 8}),
            ("set_header_text", {"kind": "set_header_text", "type": "title", "text": "Bridge Full Feature Test"}),
            ("set_meta_tag", {"kind": "set_meta_tag", "tag": "composer", "value": "maestro-musescore-bridge"}),
            ("add_part", {"kind": "add_part", "instrumentId": "violin"}),
            ("add_time_signature", {"kind": "add_time_signature", "numerator": 4, "denominator": 4, "tick": 0, "staff": 0}),
            ("add_key_signature", {"kind": "add_key_signature", "key": "C", "tick": 0, "staff": 0}),
            ("add_clef", {"kind": "add_clef", "tick": 0, "staff": 0}),
            ("add_tempo", {"kind": "add_tempo", "bpm": 112, "text": "Moderato", "tick": 0, "staff": 0}),
            ("add_note_1", {"kind": "add_note", "pitch": "C4", "duration": "quarter", "tick": 0, "staff": 0, "voice": 0}),
            ("add_note_2", {"kind": "add_note", "pitch": "E4", "duration": "quarter", "tick": 480, "staff": 0, "voice": 0}),
            ("add_rest", {"kind": "add_rest", "duration": "quarter", "tick": 960, "staff": 0, "voice": 0}),
            ("add_chord", {"kind": "add_chord", "pitches": ["G4", "B4", "D5"], "duration": "quarter", "tick": 1440, "staff": 0, "voice": 0}),
            (
                "write_sequence",
                {
                    "kind": "write_sequence",
                    "events": [
                        {"pitch": "C5", "duration": "eighth"},
                        {"pitch": "B4", "duration": "eighth"},
                        {"type": "rest", "duration": "quarter"},
                        {"pitches": ["A4", "C5", "E5"], "duration": "quarter"},
                    ],
                    "tick": 1920,
                    "staff": 0,
                    "voice": 0,
                },
            ),
            ("modify_note", {"kind": "modify_note", "tick": 0, "staff": 0, "voice": 0, "noteIndex": 0, "veloOffset": 8}),
            ("modify_chord", {"kind": "modify_chord", "tick": 1440, "staff": 0, "voice": 0, "stemDirection": 1}),
            ("add_dynamic", {"kind": "add_dynamic", "text": "ff", "tick": 1440, "staff": 0}),
            ("add_articulation", {"kind": "add_articulation", "tick": 0, "staff": 0, "voice": 0}),
            ("add_fermata", {"kind": "add_fermata", "tick": 1440, "staff": 0, "voice": 0}),
            ("add_arpeggio", {"kind": "add_arpeggio", "tick": 1440, "staff": 0, "voice": 0}),
            ("add_staff_text", {"kind": "add_staff_text", "text": "con brio", "tick": 0, "staff": 0}),
            ("add_system_text", {"kind": "add_system_text", "text": "Bridge system text", "tick": 0}),
            ("add_rehearsal_mark", {"kind": "add_rehearsal_mark", "text": "B", "tick": 1920, "staff": 0}),
            ("add_expression_text", {"kind": "add_expression_text", "text": "cantabile", "tick": 1920, "staff": 0}),
            ("add_lyrics", {"kind": "add_lyrics", "text": "la", "tick": 0, "staff": 0, "voice": 0, "verse": 0}),
            (
                "write_lyrics",
                {
                    "kind": "write_lyrics",
                    "syllables": ["la", "li", "lu", "lo", "la", "li"],
                    "tick": 0,
                    "staff": 0,
                    "voice": 0,
                    "verse": 1,
                },
            ),
            ("add_harmony", {"kind": "add_harmony", "text": "Cmaj7", "tick": 0, "staff": 0}),
            ("add_fingering", {"kind": "add_fingering", "text": "1", "tick": 0, "staff": 0, "voice": 0}),
            ("add_breath", {"kind": "add_breath", "tick": 1920, "staff": 0}),
            ("add_tuplet", {"kind": "add_tuplet", "actual": 3, "normal": 2, "totalDuration": "quarter", "tick": 2400, "staff": 0, "voice": 0}),
            ("add_layout_break", {"kind": "add_layout_break", "breakType": 0, "tick": 3840}),
            ("add_spacer", {"kind": "add_spacer", "space": 2.5, "tick": 0, "staff": 0}),
            ("modify_measure", {"kind": "modify_measure", "tick": 0, "repeatCount": 2, "userStretch": 1.15, "irregular": False}),
        ]

    def _write_progress(self, index: int, label: str, action: dict) -> None:
        payload = {"index": index, "label": label, "action": action}
        self.progress_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def on_all_features(self) -> None:
        def _do():
            action_plan = self._all_feature_actions()
            details: list[dict] = []

            for index, (label, action) in enumerate(action_plan, start=1):
                self._write_progress(index, label, action)
                result = self.client.apply_actions([action], fail_on_partial=False)
                action_result = (result.get("results") or [{}])[0]
                details.append(
                    {
                        "index": index,
                        "label": label,
                        "kind": action["kind"],
                        "ok": action_result.get("ok"),
                        "error": action_result.get("error"),
                    }
                )

            self.progress_path.write_text(
                json.dumps({"status": "complete", "count": len(action_plan)}, indent=2),
                encoding="utf-8",
            )
            ok_count = sum(1 for item in details if item["ok"] is True)
            return {
                "total_actions": len(details),
                "ok_actions": ok_count,
                "failed_actions": len(details) - ok_count,
                "details": details,
                "progress_file": str(self.progress_path),
            }

        self.run("ALL FEATURES", _do)


def main() -> None:
    root = tk.Tk()
    BridgeTesterUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
