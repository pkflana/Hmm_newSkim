import json
import math
import os

CORRECTION_NAMES = {
    "dy_ptll_njets_reweight": "dy_ptll_reweight",
    "dy_njets_reweight": "dy_njets_reweight",
}

DY_AMCATNLO_NORMALIZATION = 0.9393839712918659


def _column_names(df):
    return {str(col) for col in df.GetColumnNames()}


def is_dy_dataset(dataset_name):
    if not dataset_name:
        return False

    name = dataset_name.lower()
    return name.startswith("dy") or "dyto" in name


def is_dy_amcatnlo_dataset(dataset_name):
    if not dataset_name:
        return False
    name = dataset_name.lower()
    return is_dy_dataset(name) and "amcatnlo" in name


def load_reweight_json(json_path, expected_type=None):
    with open(json_path) as handle:
        payload = json.load(handle)

    if payload.get("schema_version") == 2 and "corrections" in payload:
        return _payload_from_correctionlib(payload, expected_type, json_path)

    if expected_type is not None and payload.get("type") != expected_type:
        raise ValueError(
            f"Unsupported DY reweight JSON type in {json_path}: "
            f"{payload.get('type')}"
        )

    return payload


def _find_correction(correction_set, expected_type, json_path):
    corrections = correction_set.get("corrections", [])
    expected_name = CORRECTION_NAMES.get(expected_type, expected_type)

    for correction in corrections:
        if correction.get("name") == expected_name:
            return correction

    if expected_type is None and len(corrections) == 1:
        return corrections[0]

    names = [correction.get("name") for correction in corrections]
    raise ValueError(
        f"Correction '{expected_name}' not found in {json_path}. "
        f"Available corrections: {names}"
    )


def _category_content(category_node, key):
    for item in category_node.get("content", []):
        if item.get("key") == key:
            return item.get("value")
    return category_node.get("default", 1.0)


def _formula_parameters(node):
    if not isinstance(node, dict) or node.get("nodetype") != "formula":
        return None
    return node.get("parameters", [])


def _ptll_payload_from_correction(correction):
    data = correction["data"]
    ggF_node = _category_content(data, 0)
    vbf_node = _category_content(data, 1)

    categories = {}
    if isinstance(ggF_node, dict):
        ggF_content = ggF_node.get("content", [])
        for name, node in zip(["ggF_0J", "ggF_1J", "ggF_ge2J"], ggF_content):
            params = _formula_parameters(node)
            if params is not None:
                categories[name] = {"fit": {"parameters": params}}

    if isinstance(vbf_node, dict):
        for node in vbf_node.get("content", []):
            params = _formula_parameters(node)
            if params is not None:
                categories["VBF_ge2J"] = {"fit": {"parameters": params}}

    return {
        "type": "dy_ptll_njets_reweight",
        "x_variable": "pt_mumu",
        "min_weight": 0.0,
        "max_weight": 5.0,
        "categories": categories,
    }


def _bins_from_binning_node(node):
    if not isinstance(node, dict) or node.get("nodetype") != "binning":
        return []

    edges = node.get("edges", [])
    content = node.get("content", [])
    bins = []
    for index, weight in enumerate(content):
        if index + 1 >= len(edges):
            break
        high = edges[index + 1]
        if float(high) >= 999.0:
            high = None
        bins.append(
            {
                "low": float(edges[index]),
                "high": high,
                "weight": float(weight),
            }
        )
    return bins


def _njets_payload_from_correction(correction):
    data = correction["data"]
    return {
        "type": "dy_njets_reweight",
        "min_weight": 0.0,
        "max_weight": 5.0,
        "categories": {
            "ggF": {"bins": _bins_from_binning_node(_category_content(data, 0))},
            "VBF": {"bins": _bins_from_binning_node(_category_content(data, 1))},
        },
    }


def _payload_from_correctionlib(correction_set, expected_type, json_path):
    correction = _find_correction(correction_set, expected_type, json_path)
    correction_name = correction.get("name")

    if correction_name == "dy_ptll_reweight":
        payload = _ptll_payload_from_correction(correction)
    elif correction_name == "dy_njets_reweight":
        payload = _njets_payload_from_correction(correction)
    else:
        raise ValueError(
            f"Unsupported DY correctionlib correction in {json_path}: "
            f"{correction_name}"
        )

    if expected_type is not None and payload.get("type") != expected_type:
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
        return cls(load_reweight_json(json_path, "dy_ptll_njets_reweight"))

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

        if is_vbf:
            return "VBF_ge2J" if njets >= 2 else None
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
        N_selectedJets=None,
        njets=None,
        is_vbf=None,
        isVBF=None,
        pt_mumu=None,
    ):
        if ptll is None:
            ptll = pt_mumu
        if ptll is None:
            raise ValueError("Pass ptll to evaluate the DY pt(ll)/NJets weight")

        if is_vbf is None:
            is_vbf = isVBF
        if nSelectedJets is None:
            nSelectedJets = N_selectedJets
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


class DYNJetsReweighter:
    def __init__(self, payload):
        self.payload = payload
        self.min_weight = float(payload.get("min_weight", 0.0))
        self.max_weight = float(payload.get("max_weight", 5.0))
        self.categories = payload.get("categories", {})

    @classmethod
    def from_json(cls, json_path):
        return cls(load_reweight_json(json_path, "dy_njets_reweight"))

    @staticmethod
    def category_from_event(nSelectedJets, category=None, is_vbf=None, isVBF=None):
        if is_vbf is None:
            is_vbf = isVBF

        if category is not None:
            category_lower = str(category).lower()
            if category_lower == "vbf":
                return "VBF"
            if category_lower == "ggf":
                return "ggF"
            raise ValueError(f"DY NJets category must be 'ggF' or 'VBF', got {category!r}")

        return "VBF" if bool(is_vbf) else "ggF"

    def evaluate(self, nSelectedJets=None, njets=None, category=None, is_vbf=None, isVBF=None):
        if nSelectedJets is None:
            nSelectedJets = njets
        if nSelectedJets is None:
            raise ValueError("Pass nSelectedJets to evaluate the DY NJets weight")

        category_key = self.category_from_event(
            nSelectedJets,
            category=category,
            is_vbf=is_vbf,
            isVBF=isVBF,
        )
        category_payload = self.categories.get(category_key)
        if category_payload is None:
            return 1.0

        njets_value = float(nSelectedJets)
        for bin_payload in category_payload.get("bins", []):
            low = float(bin_payload["low"])
            high = bin_payload.get("high")
            if njets_value < low:
                continue
            if high is not None and njets_value >= float(high):
                continue

            weight = float(bin_payload.get("weight", 1.0))
            if not math.isfinite(weight):
                return 1.0
            return min(max(weight, self.min_weight), self.max_weight)

        return 1.0


def _format_float(value):
    value = float(value)
    if not math.isfinite(value):
        return "0.0"
    return repr(value)


def _category_expression(category, condition, params, x_variable, min_weight, max_weight):
    parameters = [_format_float(value) for value in params]
    if len(parameters) != 10:
        raise ValueError(
            f"Category {category} has {len(parameters)} fit parameters, expected 10"
        )

    p = parameters

    return f"""
    if ({condition}) {{
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


def _condition_for_category(category, available_columns):
    if {"ggF", "VBF", "N_SelectedJets"}.issubset(available_columns):
        if category == "ggF_0J":
            return "ggF && N_SelectedJets == 0"
        if category == "ggF_1J":
            return "ggF && N_SelectedJets == 1"
        if category == "ggF_ge2J":
            return "ggF && N_SelectedJets >= 2"
        if category == "VBF_ge2J":
            return "VBF && N_SelectedJets >= 2"

    if category in available_columns:
        return category

    return None


def build_ptll_reweight_expression(payload, available_columns):
    x_variable = payload.get("x_variable", "pt_mumu")
    if x_variable not in available_columns:
        raise RuntimeError(
            f"DY pt(ll)/NJets reweight variable '{x_variable}' not found in RDF"
        )

    min_weight = _format_float(payload.get("min_weight", 0.0))
    max_weight = _format_float(payload.get("max_weight", 5.0))

    pieces = []
    for category, category_payload in payload.get("categories", {}).items():
        condition = _condition_for_category(category, available_columns)
        if condition is None:
            continue

        params = category_payload.get("fit", {}).get("parameters", [])
        pieces.append(
            _category_expression(
                category,
                condition,
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


def _njets_category_condition(category, available_columns):
    if "VBF" in available_columns:
        if category == "VBF":
            return "VBF"
        if category == "ggF":
            return "!VBF"

    if category in available_columns:
        return category

    return None


def build_njets_reweight_expression(payload, available_columns):
    if "N_SelectedJets" not in available_columns:
        raise RuntimeError("DY NJets reweight variable 'N_SelectedJets' not found in RDF")

    min_weight = _format_float(payload.get("min_weight", 0.0))
    max_weight = _format_float(payload.get("max_weight", 5.0))
    pieces = []

    for category, category_payload in payload.get("categories", {}).items():
        category_condition = _njets_category_condition(category, available_columns)
        if category_condition is None:
            continue

        for bin_payload in category_payload.get("bins", []):
            low = _format_float(bin_payload["low"])
            high = bin_payload.get("high")
            weight = _format_float(bin_payload.get("weight", 1.0))

            njets_condition = f"N_SelectedJets >= {low}"
            if high is not None:
                njets_condition += f" && N_SelectedJets < {_format_float(high)}"

            pieces.append(
                f"""
    if (({category_condition}) && ({njets_condition})) {{
        double weight = {weight};
        if (!std::isfinite(weight)) weight = 1.0;
        return static_cast<float>(std::min(std::max(weight, {min_weight}), {max_weight}));
    }}
                """
            )

    if not pieces:
        raise RuntimeError(
            "None of the DY NJets reweight categories are available in RDF. "
            f"JSON categories: {sorted(payload.get('categories', {}).keys())}"
        )

    return "\n".join(pieces) + "\nreturn 1.f;"


def _define_and_multiply_weight(df, expression, weight_columns, output_column, available_columns):
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


def ApplyDYAmcatnloNormalization(
    df,
    dataset_name,
    weight_columns,
    scale=DY_AMCATNLO_NORMALIZATION,
    output_column="weight_dy_amcatnlo_normalization",
):
    if not is_dy_amcatnlo_dataset(dataset_name):
        return df

    available_columns = _column_names(df)
    return _define_and_multiply_weight(
        df,
        f"static_cast<float>({float(scale):.17g})",
        weight_columns,
        output_column,
        available_columns,
    )


def ApplyDYPtLLReweight(
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

    payload = load_reweight_json(json_path, "dy_ptll_njets_reweight")
    available_columns = _column_names(df)
    expression = build_ptll_reweight_expression(payload, available_columns)
    return _define_and_multiply_weight(
        df,
        expression,
        weight_columns,
        output_column,
        available_columns,
    )


def ApplyDYNJetsReweight(
    df,
    dataset_name,
    json_path,
    weight_columns,
    output_column="weight_dy_njets",
):
    if not json_path:
        return df

    if not is_dy_dataset(dataset_name):
        return df

    if not os.path.exists(json_path):
        raise FileNotFoundError(
            f"DY NJets reweight JSON not found: {json_path}"
        )

    payload = load_reweight_json(json_path, "dy_njets_reweight")
    available_columns = _column_names(df)
    expression = build_njets_reweight_expression(payload, available_columns)
    return _define_and_multiply_weight(
        df,
        expression,
        weight_columns,
        output_column,
        available_columns,
    )


def ApplyDYPtLLNJetsReweight(*args, **kwargs):
    return ApplyDYPtLLReweight(*args, **kwargs)
