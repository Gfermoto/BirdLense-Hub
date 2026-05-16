"""Тесты inference.auto_benchmark (#371)."""

import unittest


class TestAutoBenchmark(unittest.TestCase):
    def test_measure_runs_on_stub_model(self):
        from inference.auto_benchmark import measure_binary_detector_predict_ms

        class Stub:
            def predict(self, img, verbose=False, imgsz=320):
                return []

        ms = measure_binary_detector_predict_ms(Stub(), imgsz=320)
        self.assertIsNotNone(ms)
        self.assertGreaterEqual(ms, 0.0)


if __name__ == "__main__":
    unittest.main()
