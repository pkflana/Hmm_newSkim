#!/usr/bin/env python3
"""Generate a standalone LaTeX document from a cross-section YAML file.

Handled cases
-------------
* ``crossSec`` entries, with values expressed in pb.
* ``BR`` entries, treated as dimensionless branching ratios.
* Numeric values and arithmetic expressions.
* Expressions referring to other YAML entries, e.g. ``BR_W_lnu``.
* Symmetric numerical uncertainties.
* Numerical uncertainty expressions, e.g. ``183.5 / 3``.
* Simple asymmetric percentage uncertainties, e.g. ``+0.7% - 1.1%``.
* Long/free-form uncertainty descriptions, preserved as wrapped text.
* ``reference`` and legacy ``ref`` keys.
* Optional ``comments`` column.

Requirements
------------
    pip install pyyaml

Example
-------
    python3 cross_sections_yaml_to_latex.py \\
        --input cross_sections.yaml \\
        --output cross_sections.tex \\
        --title "Cross sections and branching ratios" \\
        --margin 0.35cm \\
        --landscape

Compile with:
    latexmk -pdf cross_sections.tex
"""

from __future__ import annotations

import argparse
import ast
import math
import operator
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


# -----------------------------------------------------------------------------
# Safe arithmetic-expression evaluation
# -----------------------------------------------------------------------------

_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}

_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class ExpressionError(ValueError):
    """Raised when a YAML expression cannot be evaluated safely."""


def safe_eval_expression(expression: str, names: Mapping[str, float]) -> float:
    """Evaluate a restricted arithmetic expression.

    Only numbers, names, parentheses and +, -, *, /, ** are accepted.
    Function calls, attributes, indexing and other Python constructs are rejected.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(str(exc)) from exc

    def evaluate(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)

        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ExpressionError("only numerical constants are allowed")
            return float(node.value)

        if isinstance(node, ast.Name):
            if node.id not in names:
                raise ExpressionError(f"unknown symbol: {node.id}")
            return float(names[node.id])

        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
            left = evaluate(node.left)
            right = evaluate(node.right)
            return float(_BINARY_OPERATORS[type(node.op)](left, right))

        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
            return float(_UNARY_OPERATORS[type(node.op)](evaluate(node.operand)))

        raise ExpressionError(f"unsupported expression element: {type(node).__name__}")

    result = evaluate(tree)
    if not math.isfinite(result):
        raise ExpressionError("expression produced a non-finite value")
    return result


# -----------------------------------------------------------------------------
# Input normalization
# -----------------------------------------------------------------------------


@dataclass
class Entry:
    name: str
    quantity: str              # "crossSec" or "BR"
    raw_value: Any
    numerical_value: float | None
    raw_uncertainty: Any
    numerical_uncertainty: float | None
    reference: str
    comments: str


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Input YAML does not exist: {path}")

    with path.open("r", encoding="utf-8") as stream:
        content = yaml.safe_load(stream)

    if content is None:
        return {}
    if not isinstance(content, dict):
        raise ValueError("The YAML top level must be a mapping.")
    return content


def resolve_named_values(data: Mapping[str, Any]) -> dict[str, float]:
    """Resolve numerical cross sections and BRs, including inter-entry formulas."""
    resolved: dict[str, float] = {}
    pending: dict[str, Any] = {}

    for name, info in data.items():
        if not isinstance(info, dict):
            continue
        if "crossSec" in info:
            pending[name] = info["crossSec"]
        elif "BR" in info:
            pending[name] = info["BR"]

    # Iterate because formulas may refer to values resolved in earlier passes.
    for _ in range(len(pending) + 1):
        progress = False
        for name, raw_value in list(pending.items()):
            try:
                if isinstance(raw_value, bool):
                    continue
                if isinstance(raw_value, (int, float)):
                    value = float(raw_value)
                elif isinstance(raw_value, str):
                    value = safe_eval_expression(raw_value, resolved)
                else:
                    continue
            except (ExpressionError, ZeroDivisionError, OverflowError):
                continue

            resolved[name] = value
            del pending[name]
            progress = True

        if not pending or not progress:
            break

    return resolved


def evaluate_uncertainty(raw_uncertainty: Any, names: Mapping[str, float]) -> float | None:
    """Evaluate only uncertainties that are purely numerical/arithmetic."""
    if raw_uncertainty is None or isinstance(raw_uncertainty, bool):
        return None
    if isinstance(raw_uncertainty, (int, float)):
        return float(raw_uncertainty)
    if not isinstance(raw_uncertainty, str):
        return None

    text = raw_uncertainty.strip()
    if not text or "%" in text or re.search(r"[A-Za-z]", text):
        return None

    try:
        return safe_eval_expression(text, names)
    except (ExpressionError, ZeroDivisionError, OverflowError):
        return None


def normalize_entries(data: Mapping[str, Any]) -> list[Entry]:
    resolved = resolve_named_values(data)
    entries: list[Entry] = []

    for name, info in data.items():
        if not isinstance(info, dict):
            print(f"Warning: skipping {name!r}; entry is not a mapping.", file=sys.stderr)
            continue

        if "crossSec" in info:
            quantity = "crossSec"
            raw_value = info.get("crossSec")
        elif "BR" in info:
            quantity = "BR"
            raw_value = info.get("BR")
        else:
            print(
                f"Warning: skipping {name!r}; neither 'crossSec' nor 'BR' is present.",
                file=sys.stderr,
            )
            continue

        reference = info.get("reference", info.get("ref", ""))
        entries.append(
            Entry(
                name=str(name),
                quantity=quantity,
                raw_value=raw_value,
                numerical_value=resolved.get(name),
                raw_uncertainty=info.get("unc"),
                numerical_uncertainty=evaluate_uncertainty(info.get("unc"), resolved),
                reference="" if reference is None else str(reference),
                comments="" if info.get("comments") is None else str(info.get("comments")),
            )
        )

    return entries


# -----------------------------------------------------------------------------
# LaTeX formatting
# -----------------------------------------------------------------------------


def latex_escape(value: Any) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in text)


def latex_path(value: Any) -> str:
    """Monospace, automatically breakable text for names, paths and references."""
    text = str(value).strip().replace("{", r"\{").replace("}", r"\}")
    return rf"\path{{{text}}}"


def format_number(value: float, significant_digits: int = 8) -> str:
    if value == 0:
        return "0"
    return f"{value:.{significant_digits}g}"


def expression_to_latex(expression: Any) -> str:
    """Render a simple arithmetic expression as readable LaTeX math."""
    text = str(expression).strip()
    text = text.replace("*", r"\times ")
    text = re.sub(r"\s*/\s*", r" / ", text)
    text = text.replace("_", r"\_")
    return text


def format_value(entry: Entry, show_formula: bool) -> str:
    if entry.numerical_value is None:
        if entry.raw_value is None or str(entry.raw_value).strip() == "":
            return r"\textit{Not specified}"
        return rf"${expression_to_latex(entry.raw_value)}$"

    numerical = format_number(entry.numerical_value)
    raw = str(entry.raw_value).strip()
    raw_is_plain_number = isinstance(entry.raw_value, (int, float)) or bool(
        re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", raw)
    )

    if show_formula and not raw_is_plain_number:
        return rf"${numerical}$\newline{{\scriptsize $={expression_to_latex(raw)}$}}"
    return rf"${numerical}$"


def format_uncertainty(entry: Entry) -> str:
    raw = entry.raw_uncertainty
    if raw is None or str(raw).strip() == "":
        return r"---"

    if entry.numerical_uncertainty is not None:
        return rf"$\pm {format_number(entry.numerical_uncertainty)}$"

    text = str(raw).strip()

    # Simple asymmetric percentage: +0.7% - 1.1%
    asymmetric = re.fullmatch(
        r"\+\s*([0-9]*\.?[0-9]+)\s*%+\s*-\s*([0-9]*\.?[0-9]+)\s*%+",
        text,
    )
    if asymmetric:
        up, down = asymmetric.groups()
        return rf"$^{{+{up}\%}}_{{-{down}\%}}$"

    # Simple symmetric percentage forms: 0.8%, ±0.8%, +-0.8%, +/-0.8%
    symmetric = re.fullmatch(
        r"(?:±|\+\s*-|\+\s*/\s*-)?\s*([0-9]*\.?[0-9]+)\s*%+",
        text,
    )
    if symmetric:
        return rf"$\pm {symmetric.group(1)}\%$"

    # Complex uncertainty descriptions are intentionally not interpreted:
    # preserving labels such as scale, PDF, alpha_s, BR and filter efficiency
    # avoids silently changing their physical meaning.
    return latex_escape(text)


def quantity_label(entry: Entry) -> str:
    return r"$\sigma$ [pb]" if entry.quantity == "crossSec" else "BR"


def make_table(
    entries: list[Entry],
    caption: str,
    label: str,
    include_comments: bool,
    show_formula: bool,
) -> str:
    if include_comments:
        columns = (
            r">{\raggedright\arraybackslash}p{0.235\textwidth} "
            r">{\centering\arraybackslash}p{0.070\textwidth} "
            r">{\centering\arraybackslash}p{0.105\textwidth} "
            r">{\raggedright\arraybackslash}p{0.190\textwidth} "
            r">{\raggedright\arraybackslash}p{0.235\textwidth} "
            r">{\raggedright\arraybackslash}p{0.130\textwidth}"
        )
        header = (
            r"\textbf{Sample} & \textbf{Type} & \textbf{Value} & "
            r"\textbf{Uncertainty} & \textbf{Reference} & \textbf{Comments} \\"
        )
        continuation_columns = 6
    else:
        columns = (
            r">{\raggedright\arraybackslash}p{0.265\textwidth} "
            r">{\centering\arraybackslash}p{0.075\textwidth} "
            r">{\centering\arraybackslash}p{0.120\textwidth} "
            r">{\raggedright\arraybackslash}p{0.215\textwidth} "
            r">{\raggedright\arraybackslash}p{0.295\textwidth}"
        )
        header = (
            r"\textbf{Sample} & \textbf{Type} & \textbf{Value} & "
            r"\textbf{Uncertainty} & \textbf{Reference} \\"
        )
        continuation_columns = 5

    lines = [
        rf"\begin{{longtable}}{{{columns}}}",
        rf"\caption{{{latex_escape(caption)}}}\label{{{latex_escape(label)}}} \\",
        r"\toprule",
        header,
        r"\midrule",
        r"\endfirsthead",
        "",
        rf"\multicolumn{{{continuation_columns}}}{{c}}{{\tablename\ \thetable\ -- continued}} \\",
        r"\toprule",
        header,
        r"\midrule",
        r"\endhead",
        "",
        r"\midrule",
        rf"\multicolumn{{{continuation_columns}}}{{r}}{{Continued on next page}} \\",
        r"\endfoot",
        "",
        r"\bottomrule",
        r"\endlastfoot",
    ]

    for entry in entries:
        reference = latex_path(entry.reference) if entry.reference else r"---"
        row = [
            latex_path(entry.name),
            quantity_label(entry),
            format_value(entry, show_formula),
            format_uncertainty(entry),
            reference,
        ]
        if include_comments:
            row.append(latex_escape(entry.comments) if entry.comments else r"---")
        lines.append(" & ".join(row) + r" \\")
        lines.append(r"\addlinespace[1.5pt]")

    lines.append(r"\end{longtable}")
    return "\n".join(lines)


def make_document(
    table: str,
    title: str,
    margin: str,
    landscape: bool,
    font_size: str,
) -> str:
    orientation = ",landscape" if landscape else ""
    return "\n".join(
        [
            rf"\documentclass[{font_size},a4paper{orientation}]{{extarticle}}",
            rf"\usepackage[margin={margin}]{{geometry}}",
            r"\usepackage[T1]{fontenc}",
            r"\usepackage{lmodern}",
            r"\usepackage{microtype}",
            r"\usepackage{booktabs}",
            r"\usepackage{array}",
            r"\usepackage{xurl}",
            r"\usepackage{longtable}",
            r"\usepackage{caption}",
            r"\urlstyle{tt}",
            r"\setlength{\parindent}{0pt}",
            r"\setlength{\tabcolsep}{2.5pt}",
            r"\renewcommand{\arraystretch}{1.12}",
            r"\captionsetup{font=small,labelfont=bf,justification=centering}",
            "",
            r"\begin{document}",
            r"\begin{center}",
            rf"{{\Large\bfseries {latex_escape(title)}}}",
            r"\end{center}",
            r"\vspace{-0.3em}",
            table,
            r"\end{document}",
            "",
        ]
    )


# -----------------------------------------------------------------------------
# Command line
# -----------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a cross-section/BR YAML file into a standalone LaTeX table."
    )
    parser.add_argument("--input", type=Path, required=True, help="Input YAML file.")
    parser.add_argument("--output", type=Path, required=True, help="Output .tex file.")
    parser.add_argument(
        "--title",
        default="Cross sections and branching ratios",
        help="Document title.",
    )
    parser.add_argument(
        "--caption",
        default="Cross sections, branching ratios, uncertainties, and references.",
        help="Table caption.",
    )
    parser.add_argument("--label", default="tab:cross-sections", help="LaTeX table label.")
    parser.add_argument("--margin", default="0.35cm", help="Page margin (default: 0.35cm).")
    parser.add_argument(
        "--font-size",
        choices=["8pt", "9pt", "10pt", "11pt", "12pt"],
        default="8pt",
        help="Document font size (default: 8pt).",
    )
    parser.add_argument(
        "--landscape",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use landscape orientation (default: true).",
    )
    parser.add_argument(
        "--comments",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include the comments column (default: true).",
    )
    parser.add_argument(
        "--show-formulas",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show original formula below evaluated values (default: true).",
    )
    parser.add_argument(
        "--only",
        choices=["all", "cross-sections", "branching-ratios"],
        default="all",
        help="Select which YAML entries to include.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        data = load_yaml(args.input)
        entries = normalize_entries(data)

        if args.only == "cross-sections":
            entries = [entry for entry in entries if entry.quantity == "crossSec"]
        elif args.only == "branching-ratios":
            entries = [entry for entry in entries if entry.quantity == "BR"]

        table = make_table(
            entries=entries,
            caption=args.caption,
            label=args.label,
            include_comments=args.comments,
            show_formula=args.show_formulas,
        )
        # document = make_document(
        #     table=table,
        #     title=args.title,
        #     margin=args.margin,
        #     landscape=args.landscape,
        #     font_size=args.font_size,
        # )

        args.output.parent.mkdir(parents=True, exist_ok=True)
        # args.output.write_text(document, encoding="utf-8")
        args.output.write_text(table, encoding="utf-8")

        unresolved_values = sum(entry.numerical_value is None for entry in entries)
        complex_uncertainties = sum(
            entry.raw_uncertainty not in (None, "")
            and entry.numerical_uncertainty is None
            and not re.fullmatch(
                r"\+\s*[0-9]*\.?[0-9]+\s*%+\s*-\s*[0-9]*\.?[0-9]+\s*%+",
                str(entry.raw_uncertainty).strip(),
            )
            for entry in entries
        )

        print(f"Wrote {len(entries)} entries to {args.output}")
        print(f"Unresolved value expressions: {unresolved_values}")
        print(f"Free-form uncertainty descriptions preserved as text: {complex_uncertainties}")
        return 0

    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
