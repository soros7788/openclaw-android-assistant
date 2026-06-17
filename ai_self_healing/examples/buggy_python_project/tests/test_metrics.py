from metrics import calculate_metrics


def test_calculate_metrics_returns_mean():
    assert calculate_metrics([2, 4, 6]) == 4
