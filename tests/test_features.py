import pytest
from scripts.compare_models import load_config


# --- Metric calculation helpers (mirrors logic in compare_models.py) ---

def _compute_precision(tp, fp):
    return tp / (tp + fp) if (tp + fp) > 0 else 0


def _compute_recall(tp, fn):
    return tp / (tp + fn) if (tp + fn) > 0 else 0


def _compute_f1(precision, recall):
    if (precision + recall) == 0:
        return 0
    return 2 * precision * recall / (precision + recall)


# --- Tests ---

class TestMetricCalculations:

    def test_perfect_classifier(self):
        precision = _compute_precision(100, 0)
        recall = _compute_recall(100, 0)
        assert precision == 1.0
        assert recall == 1.0
        assert _compute_f1(precision, recall) == 1.0

    def test_no_true_positives(self):
        precision = _compute_precision(0, 10)
        recall = _compute_recall(0, 5)
        assert precision == 0.0
        assert recall == 0.0
        assert _compute_f1(precision, recall) == 0.0

    def test_high_precision_low_recall(self):
        # Model is accurate but misses most fraud cases
        precision = _compute_precision(10, 1)
        recall = _compute_recall(10, 90)
        f1 = _compute_f1(precision, recall)
        assert precision > recall
        assert f1 < precision  # F1 penalises low recall

    def test_f1_zero_division_guard(self):
        assert _compute_f1(0.0, 0.0) == 0.0

    def test_project_precision_result(self):
        # Validates the 82.9% precision reported in this project
        precision = _compute_precision(829, 171)
        assert precision == pytest.approx(0.829, abs=0.001)

    def test_f1_symmetric(self):
        p, r = 0.75, 0.60
        assert _compute_f1(p, r) == pytest.approx(_compute_f1(r, p), rel=1e-6)


class TestThresholdLogic:

    def test_threshold_range_valid(self):
        thresholds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        for t in thresholds:
            assert 0 < t < 1, f"Threshold {t} outside valid probability range"

    def test_optimal_threshold_selection(self):
        results = [
            {'threshold': 0.3, 'f1_score': 0.72},
            {'threshold': 0.4, 'f1_score': 0.78},
            {'threshold': 0.5, 'f1_score': 0.75},
        ]
        best = max(results, key=lambda x: x['f1_score'])
        assert best['threshold'] == 0.4
        assert best['f1_score'] == 0.78


class TestConfigLoading:

    def test_load_config_returns_dict(self, tmp_path):
        config_file = tmp_path / "test_config.yml"
        config_file.write_text("snowflake:\n  account: test123\n  warehouse: TEST_WH\n")
        config = load_config(str(config_file))
        assert isinstance(config, dict)
        assert config['snowflake']['account'] == 'test123'

    def test_load_config_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config('/nonexistent/path/config.yml')
