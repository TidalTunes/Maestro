from __future__ import annotations

import json
from pathlib import Path
import sys


def _load_module_function(script_path: Path, function_name: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location("generated_maestro_score", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load generated score module.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    function = getattr(module, function_name, None)
    if function is None or not callable(function):
        raise RuntimeError(f"Generated code must define {function_name}(...).")
    return function


def run_generate(script_path: Path, output_path: Path) -> None:
    build_score = _load_module_function(script_path, "build_score")
    build_score(str(output_path))


def run_edit(base_script_path: Path, edit_script_path: Path, output_path: Path) -> None:
    namespace: dict[str, object] = {}
    exec(base_script_path.read_text(encoding="utf-8"), namespace)

    base_score = namespace.get("score")
    if base_score is None:
        raise RuntimeError("Imported score context must define a global `score` object.")
    if not hasattr(base_score, "clone_shell") or not hasattr(base_score, "to_delta_actions"):
        raise RuntimeError("Imported score context must provide maestroxml live-edit helpers.")

    score = base_score.clone_shell()
    part_map = {id(source): target for source, target in zip(base_score.parts, score.parts)}

    for name, value in list(namespace.items()):
        if value is base_score:
            namespace[name] = score
            continue

        mapped_part = part_map.get(id(value))
        if mapped_part is not None:
            namespace[name] = mapped_part
            continue

        owner = getattr(value, "part", None)
        voice = getattr(value, "voice", None)
        staff = getattr(value, "staff", None)
        mapped_owner = part_map.get(id(owner))
        if mapped_owner is not None and isinstance(voice, int) and isinstance(staff, int):
            namespace[name] = mapped_owner.voice(voice, staff)

    namespace["score"] = score

    exec(edit_script_path.read_text(encoding="utf-8"), namespace)

    apply_changes = namespace.get("apply_changes")
    if apply_changes is None or not callable(apply_changes):
        raise RuntimeError("Generated code must define apply_changes(score).")

    apply_changes(score)
    output_path.write_text(
        json.dumps(score.to_delta_actions(base_score), indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        raise SystemExit("Usage: maestro-runtime-runner <generate|edit> ...")

    mode = args.pop(0)
    if mode == "generate":
        if len(args) != 2:
            raise SystemExit("Usage: maestro-runtime-runner generate <script_path> <output_path>")
        run_generate(Path(args[0]), Path(args[1]))
        return 0

    if mode == "edit":
        if len(args) != 3:
            raise SystemExit(
                "Usage: maestro-runtime-runner edit <base_script_path> <edit_script_path> <output_path>"
            )
        run_edit(Path(args[0]), Path(args[1]), Path(args[2]))
        return 0

    raise SystemExit(f"Unknown mode: {mode}")


if __name__ == "__main__":
    raise SystemExit(main())
