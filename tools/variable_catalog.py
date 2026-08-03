"""Discover RDataFrame columns for the ``hmumu vars`` command."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SOURCE_AREAS = ("analysis", "common", "corrections", "histograms")
SOURCE_SUFFIXES = {".py", ".cc", ".cpp", ".h", ".hpp"}
CONFIG_SUFFIXES = {".yaml", ".yml", ".toml"}
NAME_TOKEN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


@dataclass(frozen=True)
class ColumnDefinition:
    """A statically discoverable call to RDataFrame.Define."""

    name: str
    path: Path
    line: int
    producer: str
    expression: str | None
    dynamic: bool = False

    @property
    def dependencies(self) -> tuple[str, ...]:
        if not self.expression:
            return ()
        return tuple(dict.fromkeys(NAME_TOKEN.findall(self.expression)))


def _literal_or_template(node: ast.AST) -> tuple[str | None, bool]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, False
    if isinstance(node, ast.JoinedStr):
        chunks = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                chunks.append(str(value.value))
            else:
                chunks.append("{...}")
        return "".join(chunks), True
    if isinstance(node, ast.Name):
        return f"<{node.id}>", True
    return None, True


class _DefineVisitor(ast.NodeVisitor):
    def __init__(self, path: Path):
        self.path = path
        self.scope: list[str] = []
        self.definitions: list[ColumnDefinition] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        function = node.func
        if (
            isinstance(function, ast.Attribute)
            and function.attr in {"Define", "Redefine"}
            and len(node.args) >= 1
        ):
            name, dynamic = _literal_or_template(node.args[0])
            expression = None
            if len(node.args) >= 2:
                expression, _ = _literal_or_template(node.args[1])
            if name:
                self.definitions.append(
                    ColumnDefinition(
                        name=name,
                        path=self.path,
                        line=node.lineno,
                        producer=".".join(self.scope) or "<module>",
                        expression=expression,
                        dynamic=dynamic,
                    )
                )
        self.generic_visit(node)


def iter_framework_files(repo: Path) -> Iterable[Path]:
    for area in SOURCE_AREAS:
        root = repo / area
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in SOURCE_SUFFIXES:
                yield path


def discover_definitions(repo: Path) -> list[ColumnDefinition]:
    definitions: list[ColumnDefinition] = []
    for path in iter_framework_files(repo):
        if path.suffix != ".py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        relative_path = path.relative_to(repo)
        visitor = _DefineVisitor(relative_path)
        visitor.visit(tree)
        definitions.extend(visitor.definitions)
    return sorted(definitions, key=lambda item: (item.name, str(item.path), item.line))


def name_matches(pattern: str, candidate: str) -> bool:
    """Match exact names and templates such as ``mu{...}_pt``."""
    if candidate == pattern:
        return True
    if "{...}" not in candidate:
        return False
    template = re.escape(candidate).replace(re.escape("{...}"), ".+")
    return re.fullmatch(template, pattern) is not None


def definitions_for(
    definitions: Iterable[ColumnDefinition], variable: str
) -> list[ColumnDefinition]:
    return [item for item in definitions if name_matches(variable, item.name)]


def configured_in(repo: Path, variable: str) -> list[tuple[Path, int, str]]:
    matches = []
    config_root = repo / "config"
    for path in config_root.rglob("*"):
        if not path.is_file() or path.suffix not in CONFIG_SUFFIXES:
            continue
        for line_number, text in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            if re.search(
                rf"(?<![A-Za-z0-9_]){re.escape(variable)}(?![A-Za-z0-9_])",
                text,
            ):
                matches.append((path.relative_to(repo), line_number, text.strip()))
    return matches


def dependency_names(
    definition: ColumnDefinition, known_names: Iterable[str]
) -> list[str]:
    known = set(known_names)
    return [name for name in definition.dependencies if name in known]
