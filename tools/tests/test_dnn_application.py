import unittest

import numpy as np

from common.dnn_application import DNNApplication, validate_predictions


class FakeDataFrame:
    def __init__(self, columns=()):
        self.columns = list(columns)
        self.definitions = []

    def GetColumnNames(self):
        return self.columns

    def Define(self, name, expression):
        self.definitions.append((name, expression))
        self.columns.append(name)
        return self


class DNNApplicationTest(unittest.TestCase):
    def application(self, era):
        application = DNNApplication.__new__(DNNApplication)
        application.era = era
        application.btag_algo = "PNet"
        return application

    def test_era_code_is_defined_for_every_supported_era(self):
        for era, expected_code in DNNApplication.ERA_CODES.items():
            with self.subTest(era=era):
                dataframe = FakeDataFrame()
                self.application(era).define_feature_aliases(dataframe)
                self.assertIn(("era_code", str(expected_code)), dataframe.definitions)

    def test_existing_era_code_is_preserved(self):
        dataframe = FakeDataFrame(["era_code"])
        self.application("Run3_2024").define_feature_aliases(dataframe)
        self.assertNotIn("era_code", [name for name, _ in dataframe.definitions])

    def test_unknown_era_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Cannot define era_code"):
            self.application("Run3_unknown").define_feature_aliases(FakeDataFrame())

    def test_saturated_predictions_are_rejected(self):
        for predictions in (np.zeros(4), np.ones(4)):
            with self.subTest(predictions=predictions):
                with self.assertRaisesRegex(RuntimeError, "saturated"):
                    validate_predictions(predictions, "DNN")

    def test_non_saturated_predictions_are_accepted(self):
        validate_predictions(np.array([0.1, 0.5, 0.9]), "DNN")

    def test_empty_vbf_prediction_selection_is_accepted(self):
        validate_predictions(np.array([], dtype=np.float32), "DNN", "legacy")


if __name__ == "__main__":
    unittest.main()
