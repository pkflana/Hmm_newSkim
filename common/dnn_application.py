import os
import sys

import numpy as np
import ROOT
import yaml

if __name__ == "__main__":
    sys.path.append(os.environ["ANALYSIS_PATH"])


_REGISTRY_DECLARED = False


def _declare_prediction_registry():
    global _REGISTRY_DECLARED
    if _REGISTRY_DECLARED:
        return
    ROOT.gInterpreter.Declare(
        """
        #include <stdexcept>
        #include <unordered_map>
        #include <vector>

        namespace dnn_application {
            std::vector<std::unordered_map<ULong64_t, float>>& payloads() {
                static std::vector<std::unordered_map<ULong64_t, float>> data;
                return data;
            }

            std::size_t registerPayload(const std::vector<ULong64_t>& keys, const std::vector<float>& values) {
                if (keys.size() != values.size()) {
                    throw std::runtime_error("DNN prediction keys and values have different sizes");
                }
                std::unordered_map<ULong64_t, float> payload;
                payload.reserve(values.size());
                for (std::size_t idx = 0; idx < values.size(); ++idx) {
                    payload[keys[idx]] = values[idx];
                }
                payloads().push_back(std::move(payload));
                return payloads().size() - 1;
            }

            float getPrediction(std::size_t payload_id, ULong64_t event_key) {
                const auto& values = payloads().at(payload_id);
                const auto it = values.find(event_key);
                if (it == values.end()) {
                    throw std::runtime_error("DNN prediction lookup failed for event key");
                }
                return it->second;
            }
        }
        """
    )
    _REGISTRY_DECLARED = True


def _parse_column_names(columns_config):
    if "features" in columns_config:
        return list(dict.fromkeys(columns_config["features"]))

    features = []
    for mu_idx in [1, 2]:
        for mu_var in columns_config["Muon"]:
            features.append(mu_var.format(mu_idx))
    features.extend(columns_config["MuPair"])
    features.extend(columns_config["MuJet"])
    for j_idx in [1, 2]:
        for jet_var in columns_config["VBFJet"]:
            features.append(f"j{j_idx}_{jet_var}")
    features.extend(columns_config["VBFJetPair"])
    return list(dict.fromkeys(features))


def _load_toml(path):
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            tomllib = None

    if tomllib is not None:
        with open(path, "rb") as f:
            return tomllib.load(f)

    config = {}
    current_section = None
    with open(path, "r") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line.strip("[]")
                config[current_section] = {}
                continue
            if current_section and "=" in line:
                key, value = [part.strip() for part in line.split("=", 1)]
                if value.isdigit():
                    value = int(value)
                config[current_section][key] = value
    return config


class DNNApplication:
    def __init__(self, payload_name="DNN", base_dir=None, btag_algo="PNet"):
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError("onnxruntime is required for DNN application. Run 'source env.sh' first.") from exc

        self.ort = ort
        self.payload_name = payload_name
        self.btag_algo = btag_algo
        self.base_dir = base_dir or os.environ["ANALYSIS_PATH"]
        self.models_dir = os.path.join(self.base_dir, "common", "models")
        self.config_dir = os.path.join(self.base_dir, "common", "dnn_configs")
        self.parity, self.input_features = self._load_config()
        self.models = self._load_models()

    def _load_config(self):
        config = _load_toml(os.path.join(self.config_dir, "config.toml"))
        with open(os.path.join(self.config_dir, "columns_config.yaml"), "r") as f:
            columns_config = yaml.safe_load(f)
        features = _parse_column_names(columns_config.get("vars_to_save", columns_config))
        features = [feature.format(algo=self.btag_algo) for feature in features]
        return config["kfold"]["k"], features

    def _load_models(self):
        options = self.ort.SessionOptions()
        options.graph_optimization_level = self.ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        models = []
        for idx in range(self.parity):
            model_path = os.path.join(self.models_dir, f"trained_model_{idx}.onnx")
            models.append(
                self.ort.InferenceSession(
                    model_path,
                    sess_options=options,
                    providers=["CPUExecutionProvider"],
                )
            )
        return models

    def define_feature_aliases(self, df):
        columns = {str(col) for col in df.GetColumnNames()}

        aliases = {
            "pt_jj": "pt_vbfj1j2",
            "Zepperfield_Var": "Zeppenfeld_Var",
        }
        for idx in [1, 2]:
            for var in ["eta", "pt", f"btag{self.btag_algo}QvG"]:
                aliases[f"j{idx}_{var}"] = f"vbfjet{idx}_{var}"

        for alias, source in aliases.items():
            if alias not in columns and source in columns:
                df = df.Define(alias, source)
                columns.add(alias)

        if "minDeltaEtaSigned" not in columns and {"HasVBF", "eta_mumu", "vbfjet1_eta", "vbfjet2_eta"} <= columns:
            df = df.Define(
                "minDeltaEtaSigned",
                "if (HasVBF) return static_cast<float>(std::min(eta_mumu - vbfjet1_eta, eta_mumu - vbfjet2_eta)); return -10000.f;",
            )
            columns.add("minDeltaEtaSigned")

        if "FullEventId" not in columns:
            df = df.Define("FullEventId", "static_cast<ULong64_t>(rdfentry_)")
            columns.add("FullEventId")

        if "DNNEntryKey" not in columns:
            df = df.Define("DNNEntryKey", "static_cast<ULong64_t>(rdfentry_)")

        return df

    def apply(self, df):
        output_name = f"{self.payload_name}_NNOutput"
        if output_name in {str(col) for col in df.GetColumnNames()}:
            return df

        df = self.define_feature_aliases(df)
        columns = {str(col) for col in df.GetColumnNames()}
        missing = [feature for feature in self.input_features if feature not in columns]
        if missing:
            raise RuntimeError(f"Missing DNN input feature columns: {missing}")

        arrays = df.AsNumpy(["DNNEntryKey", "FullEventId"] + self.input_features)
        n_events = len(arrays["FullEventId"])
        if n_events == 0:
            predictions = np.array([], dtype=np.float32)
        else:
            input_array = np.column_stack([arrays[name] for name in self.input_features]).astype(np.float64)
            input_array = np.nan_to_num(input_array, nan=-10000.0, posinf=-10000.0, neginf=-10000.0)
            event_number = np.asarray(arrays["FullEventId"], dtype=np.uint64)
            all_predictions = np.zeros((n_events, self.parity), dtype=np.float64)

            for parity_idx, session in enumerate(self.models):
                input_name = session.get_inputs()[0].name
                output_name_onnx = session.get_outputs()[0].name
                pred = session.run([output_name_onnx], {input_name: input_array})[0].reshape(n_events)
                pred = np.nan_to_num(pred, nan=0.0, posinf=0.0, neginf=0.0)
                pred[(event_number % self.parity) != parity_idx] = 0.0
                all_predictions[:, parity_idx] = pred

            predictions = np.sum(all_predictions, axis=1).astype(np.float32)

        _declare_prediction_registry()
        keys = ROOT.std.vector("ULong64_t")()
        values = ROOT.std.vector("float")()
        for key, value in zip(arrays["DNNEntryKey"], predictions):
            keys.push_back(int(key))
            values.push_back(float(value))
        payload_id = int(ROOT.dnn_application.registerPayload(keys, values))
        return df.Define(output_name, f"dnn_application::getPrediction({payload_id}, DNNEntryKey)")


def ApplyDNN(df, payload_names=None, btag_algo="PNet"):
    payload_names = payload_names or ["DNN"]
    for payload_name in payload_names:
        df = DNNApplication(payload_name=payload_name, btag_algo=btag_algo).apply(df)
    return df
