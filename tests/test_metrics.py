import pytest
from scripts.compare_models import load_config
from scripts.evaluate_model import calculate_metrics


class TestCalculateMetrics:

    def test_perfect_classifier(self):
        metrics = calculate_metrics({'tp': 100, 'fp': 0, 'fn': 0, 'tn': 900})
        assert metrics['precision'] == 1.0
        assert metrics['recall'] == 1.0
        assert metrics['f1_score'] == 1.0
        assert metrics['accuracy'] == 1.0

    def test_no_true_positives(self):
        metrics = calculate_metrics({'tp': 0, 'fp': 10, 'fn': 5, 'tn': 985})
        assert metrics['precision'] == 0
        assert metrics['recall'] == 0
        assert metrics['f1_score'] == 0

    def test_all_zero_confusion_matrix(self):
        # Empty predictions table should not divide by zero
        metrics = calculate_metrics({'tp': 0, 'fp': 0, 'fn': 0, 'tn': 0})
        assert metrics['precision'] == 0
        assert metrics['recall'] == 0
        assert metrics['f1_score'] == 0
        assert metrics['accuracy'] == 0

    def test_known_values(self):
        # 80 caught, 20 false alarms, 40 missed
        metrics = calculate_metrics({'tp': 80, 'fp': 20, 'fn': 40, 'tn': 860})
        assert metrics['precision'] == pytest.approx(0.8)
        assert metrics['recall'] == pytest.approx(0.6667, abs=0.0001)
        assert metrics['f1_score'] == pytest.approx(0.7273, abs=0.0001)

    def test_f1_between_precision_and_recall(self):
        metrics = calculate_metrics({'tp': 50, 'fp': 5, 'fn': 100, 'tn': 845})
        low, high = sorted([metrics['precision'], metrics['recall']])
        assert low <= metrics['f1_score'] <= high

    def test_specificity(self):
        metrics = calculate_metrics({'tp': 10, 'fp': 30, 'fn': 10, 'tn': 70})
        assert metrics['specificity'] == pytest.approx(0.7)


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
