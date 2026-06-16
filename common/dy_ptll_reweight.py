import json
import math
import os


def _column_names(df):
    return {str(col) for col in df.GetColumnNames()}


def is_dy_dataset(dataset_name):
    if not dataset_name:
        return False

    name = dataset_name.lower()
    return name.startswith("dy") or "dyto" in name


def load_reweight_json(json_path):
    with open(json_path) as handle:
        payload = json.load(handle)

    if payload.get("type") != "dy_ptll_njets_reweight":
        raise ValueError(
            f"Unsupported DY reweight JSON type in {json_path}: "
            f"{payload.get('type')}"
        )

    return payload


def evaluate_formula(x, params):
    if len(params) != 10:
        raise ValueError(f"Expected 10 fit parameters, got {len(params)}")

    x = max(float(x), 0.0)
    p = [float(value) for value in params]
    sigma1 = max(p[3], 1e-6)
    sigma2 = max(p[6], 1e-6)
    x0 = max(p[8], 1e-6)
    floor_x = max(x, p[8])

    return (
        p[0]
        + p[1] * math.exp(-0.5 * ((x - p[2]) / sigma1) ** 2)
        + p[4] * math.exp(-0.5 * ((x - p[5]) / sigma2) ** 2)
        + p[7] * (floor_x / x0) ** (-p[9])
    )


class DYPtLLNJetsReweighter:
    def __init__(self, payload):
        self.payload = payload
        self.min_weight = float(payload.get("min_weight", 0.0))
        self.max_weight = float(payload.get("max_weight", 5.0))
        self.categories = payload.get("categories", {})

    @classmethod
    def from_json(cls, json_path):
        return cls(load_reweight_json(json_path))

    @staticmethod
    def category_from_event(nSelectedJets, category=None, is_vbf=None):
        njets = int(nSelectedJets)

        if category is not None:
            category = str(category)
            category_lower = category.lower()
            if category_lower == "vbf":
                return "VBF_ge2J" if njets >= 2 else None
            if category_lower == "ggf":
                if njets <= 0:
                    return "ggF_0J"
                if njets == 1:
                    return "ggF_1J"
                return "ggF_ge2J"
            if category in {"ggF_0J", "ggF_1J", "ggF_ge2J", "VBF_ge2J"}:
                return category

            raise ValueError(
                "DY pt(ll)/NJets category must be 'ggF', 'VBF', "
                f"or an internal category, got {category!r}"
            )

        if is_vbf and njets >= 2:
            return "VBF_ge2J"
        if njets <= 0:
            return "ggF_0J"
        if njets == 1:
            return "ggF_1J"
        return "ggF_ge2J"

    def evaluate(
        self,
        ptll=None,
        category=None,
        nSelectedJets=None,
        njets=None,
        is_vbf=None,
    ):
        if ptll is None:
            raise ValueError("Pass ptll to evaluate the DY pt(ll)/NJets weight")

        if nSelectedJets is None:
            nSelectedJets = njets
        if nSelectedJets is None:
            raise ValueError("Pass nSelectedJets to evaluate the DY pt(ll)/NJets weight")

        internal_category = self.category_from_event(
            nSelectedJets,
            category=category,
            is_vbf=is_vbf,
        )
        if internal_category is None:
            return 1.0

        category_payload = self.categories.get(internal_category)
        if category_payload is None:
            return 1.0

        params = category_payload.get("fit", {}).get("parameters", [])
        weight = evaluate_formula(ptll, params)
        if not math.isfinite(weight):
            return 1.0

        return min(max(weight, self.min_weight), self.max_weight)


def _format_float(value):
    value = float(value)
    if not math.isfinite(value):
        return "0.0"
    return repr(value)


def _category_expression(category, params, x_variable, min_weight, max_weight):
    parameters = [_format_float(value) for value in params]
    if len(parameters) != 10:
        raise ValueError(
            f"Category {category} has {len(parameters)} fit parameters, expected 10"
        )

    p = parameters

    return f"""
    if ({category}) {{
        const double x = std::max(static_cast<double>({x_variable}), 0.0);
        const double floor_x = std::max(x, {p[8]});
        double weight =
            {p[0]}
            + {p[1]} * std::exp(-0.5 * std::pow((x - {p[2]}) / std::max({p[3]}, 1e-6), 2.0))
            + {p[4]} * std::exp(-0.5 * std::pow((x - {p[5]}) / std::max({p[6]}, 1e-6), 2.0))
            + {p[7]} * std::pow(floor_x / std::max({p[8]}, 1e-6), -{p[9]});
        if (!std::isfinite(weight)) weight = 1.0;
        return static_cast<float>(std::min(std::max(weight, {min_weight}), {max_weight}));
    }}
    """


def build_reweight_expression(payload, available_columns):
    x_variable = payload.get("x_variable", "pt_mumu")
    if x_variable not in available_columns:
        raise RuntimeError(
            f"DY pt(ll)/NJets reweight variable '{x_variable}' not found in RDF"
        )

    min_weight = _format_float(payload.get("min_weight", 0.0))
    max_weight = _format_float(payload.get("max_weight", 5.0))

    pieces = []
    for category, category_payload in payload.get("categories", {}).items():
        if category not in available_columns:
            continue

        params = category_payload.get("fit", {}).get("parameters", [])
        pieces.append(
            _category_expression(
                category,
                params,
                x_variable,
                min_weight,
                max_weight,
            )
        )

    if not pieces:
        raise RuntimeError(
            "None of the DY pt(ll)/NJets reweight categories are available in RDF. "
            f"JSON categories: {sorted(payload.get('categories', {}).keys())}"
        )

    return "\n".join(pieces) + "\nreturn 1.f;"


def ApplyDYPtLLNJetsReweight(
    df,
    dataset_name,
    json_path,
    weight_columns,
    output_column="weight_dy_ptll_njets",
):
    if not json_path:
        return df

    if not is_dy_dataset(dataset_name):
        return df

    if not os.path.exists(json_path):
        raise FileNotFoundError(
            f"DY pt(ll)/NJets reweight JSON not found: {json_path}"
        )

    payload = load_reweight_json(json_path)
    available_columns = _column_names(df)
    expression = build_reweight_expression(payload, available_columns)

    if output_column in available_columns:
        df = df.Redefine(output_column, expression)
    else:
        df = df.Define(output_column, expression)
        available_columns.add(output_column)

    for weight_column in sorted(set(weight_columns)):
        if weight_column not in available_columns:
            continue
        df = df.Redefine(
            weight_column,
            f"static_cast<float>({weight_column} * {output_column})",
        )

    return df
