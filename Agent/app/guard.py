from __future__ import annotations

import ast


ALLOWED_IMPORTS = {"__future__", "maestroxml", "pathlib"}
SUPPORTED_DURATION_NAMES = {
    "whole",
    "half",
    "quarter",
    "eighth",
    "8th",
    "16th",
    "sixteenth",
    "32nd",
    "thirty-second",
    "64th",
    "sixty-fourth",
}
NOTE_METHOD_NAMES = {"note", "notes", "rest", "chord"}
DISALLOWED_CALL_NAMES = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "input",
    "breakpoint",
    "open",
}
DISALLOWED_ATTRIBUTE_CALLS = {
    "chmod",
    "chown",
    "hardlink_to",
    "mkdir",
    "open",
    "popen",
    "read_bytes",
    "read_text",
    "remove",
    "rename",
    "replace",
    "rmdir",
    "run",
    "symlink_to",
    "system",
    "touch",
    "unlink",
    "write_bytes",
    "write_text",
}


class CodeGuardError(RuntimeError):
    """Raised when generated code violates the runtime contract."""


def _root_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _root_name(node.value)
    return None


def _string_constant(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _validate_duration_literal(value: str, source: str) -> None:
    if value not in SUPPORTED_DURATION_NAMES:
        supported = ", ".join(sorted(SUPPORTED_DURATION_NAMES))
        raise CodeGuardError(
            f"Unsupported duration literal {value!r} in generated code ({source}). "
            f"Supported duration names: {supported}."
        )


def validate_generated_code(code: str) -> None:
    stripped = code.strip()
    if not stripped:
        raise CodeGuardError("The model returned an empty response instead of Python code.")
    if "```" in code:
        raise CodeGuardError("The model returned Markdown fences; raw Python source was required.")

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise CodeGuardError(f"Generated Python is not syntactically valid: {exc.msg}") from exc

    public_functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    build_score_functions = [node for node in public_functions if node.name == "build_score"]
    if len(build_score_functions) != 1:
        raise CodeGuardError("Generated code must define exactly one build_score(output_path) function.")

    if len(public_functions) != 1:
        raise CodeGuardError("Generated code must not define helper functions outside build_score().")

    build_score = build_score_functions[0]
    if len(build_score.args.args) != 1 or build_score.args.args[0].arg != "output_path":
        raise CodeGuardError("build_score must accept exactly one argument named output_path.")

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        raise CodeGuardError("Generated code must not execute statements at import time.")

    has_maestroxml_import = False
    has_output_path_reference = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in ALLOWED_IMPORTS:
                    raise CodeGuardError(f"Disallowed import in generated code: {alias.name}")
                if root == "maestroxml":
                    has_maestroxml_import = True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            if root not in ALLOWED_IMPORTS:
                raise CodeGuardError(f"Disallowed import in generated code: {module}")
            if root == "maestroxml":
                has_maestroxml_import = True
        elif isinstance(node, ast.Call):
            call_name = _call_name(node.func)
            if call_name in DISALLOWED_CALL_NAMES:
                raise CodeGuardError(f"Disallowed function call in generated code: {call_name}")
            if call_name.startswith("os.") or call_name.startswith("subprocess."):
                raise CodeGuardError(f"Disallowed function call in generated code: {call_name}")
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in NOTE_METHOD_NAMES and node.args:
                    duration = _string_constant(node.args[0])
                    if duration is not None:
                        _validate_duration_literal(duration, f"{node.func.attr}(...) call")
                if node.func.attr in DISALLOWED_ATTRIBUTE_CALLS:
                    raise CodeGuardError(
                        f"Disallowed attribute call in generated code: {node.func.attr}"
                    )
                root = _root_name(node.func.value)
                if root in {"subprocess", "shutil", "socket"}:
                    raise CodeGuardError(
                        f"Disallowed module usage in generated code: {root}.{node.func.attr}"
                    )
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if _string_constant(key) == "duration":
                    duration = _string_constant(value)
                    if duration is not None:
                        _validate_duration_literal(duration, "duration field")
        elif isinstance(node, ast.Name) and node.id == "output_path":
            has_output_path_reference = True

    if not has_maestroxml_import:
        raise CodeGuardError("Generated code must import `maestroxml`.")
    if not has_output_path_reference:
        raise CodeGuardError("Generated code must reference the build_score(output_path) argument.")
