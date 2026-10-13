"""
Tests for the deterministic evaluation engine.

Covers all 10 required test scenarios:
1.  Profit Factor PASS
2.  Profit Factor FAIL
3.  Drawdown PASS
4.  Drawdown FAIL
5.  Win Rate PASS
6.  Win Rate FAIL
7.  Missing Win Rate → INSUFFICIENT_DATA
8.  Overall QUALIFIED
9.  Overall REJECTED
10. Overall INSUFFICIENT_DATA
"""

import pytest
from app.services.evaluation.evaluator import evaluate_experiment
from app.services.evaluation.rules import PASS, FAIL, INSUFFICIENT_DATA


def _eval(pf=None, dd=None, wr=None):
    """Helper to build metrics dict and evaluate."""
    metrics = {}
    if pf is not None:
        metrics["profit_factor"] = pf
    if dd is not None:
        metrics["equity_drawdown_pct"] = dd
    if wr is not None:
        metrics["win_rate"] = wr
    return evaluate_experiment(metrics)


class TestProfitFactorRule:
    """Tests 1–2: Profit Factor"""

    def test_pf_above_threshold_passes(self):
        """PF = 2.1 > 1.5 → PASS"""
        result = _eval(pf=2.1, dd=10.0, wr=70.0)
        pf_rule = next(r for r in result.rule_results if r.rule.metric == "profit_factor")
        assert pf_rule.status == PASS

    def test_pf_below_threshold_fails(self):
        """PF = 1.2 < 1.5 → FAIL"""
        result = _eval(pf=1.2, dd=10.0, wr=70.0)
        pf_rule = next(r for r in result.rule_results if r.rule.metric == "profit_factor")
        assert pf_rule.status == FAIL

    def test_pf_exactly_at_threshold_fails(self):
        """PF = 1.5 is NOT > 1.5 → FAIL (strict greater-than)"""
        result = _eval(pf=1.5, dd=10.0, wr=70.0)
        pf_rule = next(r for r in result.rule_results if r.rule.metric == "profit_factor")
        assert pf_rule.status == FAIL

    def test_pf_actual_value_preserved(self):
        result = _eval(pf=2.75, dd=10.0, wr=70.0)
        pf_rule = next(r for r in result.rule_results if r.rule.metric == "profit_factor")
        assert pf_rule.actual_value == pytest.approx(2.75)


class TestDrawdownRule:
    """Tests 3–4: Equity Drawdown %"""

    def test_dd_below_threshold_passes(self):
        """DD = 12% < 25% → PASS"""
        result = _eval(pf=2.0, dd=12.4, wr=70.0)
        dd_rule = next(r for r in result.rule_results if r.rule.metric == "equity_drawdown_pct")
        assert dd_rule.status == PASS

    def test_dd_above_threshold_fails(self):
        """DD = 30% > 25% → FAIL"""
        result = _eval(pf=2.0, dd=30.0, wr=70.0)
        dd_rule = next(r for r in result.rule_results if r.rule.metric == "equity_drawdown_pct")
        assert dd_rule.status == FAIL

    def test_dd_exactly_at_threshold_fails(self):
        """DD = 25% is NOT < 25% → FAIL (strict less-than)"""
        result = _eval(pf=2.0, dd=25.0, wr=70.0)
        dd_rule = next(r for r in result.rule_results if r.rule.metric == "equity_drawdown_pct")
        assert dd_rule.status == FAIL

    def test_dd_actual_value_preserved(self):
        result = _eval(pf=2.0, dd=14.56, wr=70.0)
        dd_rule = next(r for r in result.rule_results if r.rule.metric == "equity_drawdown_pct")
        assert dd_rule.actual_value == pytest.approx(14.56)


class TestWinRateRule:
    """Tests 5–7: Win Rate"""

    def test_wr_above_threshold_passes(self):
        """WR = 75% > 60% → PASS"""
        result = _eval(pf=2.0, dd=10.0, wr=75.0)
        wr_rule = next(r for r in result.rule_results if r.rule.metric == "win_rate")
        assert wr_rule.status == PASS

    def test_wr_below_threshold_fails(self):
        """WR = 45% < 60% → FAIL"""
        result = _eval(pf=2.0, dd=10.0, wr=45.0)
        wr_rule = next(r for r in result.rule_results if r.rule.metric == "win_rate")
        assert wr_rule.status == FAIL

    def test_wr_missing_is_insufficient_data(self):
        """Win Rate absent → INSUFFICIENT_DATA (not FAIL, not PASS)"""
        result = _eval(pf=2.1, dd=12.0)  # no wr
        wr_rule = next(r for r in result.rule_results if r.rule.metric == "win_rate")
        assert wr_rule.status == INSUFFICIENT_DATA
        assert wr_rule.actual_value is None

    def test_wr_missing_actual_value_is_none(self):
        result = _eval(pf=2.0, dd=10.0)
        wr_rule = next(r for r in result.rule_results if r.rule.metric == "win_rate")
        assert wr_rule.actual_value is None


class TestOverallStatus:
    """Tests 8–10: Overall qualification status"""

    def test_overall_qualified_when_all_pass(self):
        """
        PF PASS, DD PASS, WR PASS → QUALIFIED
        """
        result = _eval(pf=2.0, dd=10.0, wr=70.0)
        assert result.overall_status == "QUALIFIED"

    def test_overall_rejected_when_any_fail(self):
        """
        PF PASS, DD FAIL, WR PASS → REJECTED

        A single definitive FAIL overrides everything else.
        """
        result = _eval(pf=2.0, dd=35.0, wr=70.0)
        assert result.overall_status == "REJECTED"

    def test_overall_rejected_when_pf_fails(self):
        result = _eval(pf=1.0, dd=10.0, wr=70.0)
        assert result.overall_status == "REJECTED"

    def test_overall_rejected_when_wr_fails(self):
        result = _eval(pf=2.0, dd=10.0, wr=40.0)
        assert result.overall_status == "REJECTED"

    def test_overall_insufficient_data_when_wr_missing(self):
        """
        PF PASS, DD PASS, WR MISSING → INSUFFICIENT_DATA

        This is NOT QUALIFIED because we cannot confirm WR rule.
        """
        result = _eval(pf=2.0, dd=10.0)
        assert result.overall_status == "INSUFFICIENT_DATA"

    def test_overall_rejected_even_if_wr_missing(self):
        """
        PF PASS, DD FAIL, WR MISSING → REJECTED

        A definitive FAIL overrides INSUFFICIENT_DATA.
        """
        result = _eval(pf=2.0, dd=35.0)
        assert result.overall_status == "REJECTED"

    def test_overall_rejected_pf_fail_wr_missing(self):
        """
        PF FAIL, DD PASS, WR MISSING → REJECTED
        """
        result = _eval(pf=1.0, dd=10.0)
        assert result.overall_status == "REJECTED"

    def test_evaluation_response_has_three_rules(self):
        """Evaluation always returns all three rule results."""
        result = _eval(pf=2.0, dd=10.0, wr=70.0)
        assert len(result.rule_results) == 3

    def test_evaluation_to_dict_structure(self):
        """to_dict() returns the expected structure."""
        result = _eval(pf=2.1, dd=12.4)
        d = result.to_dict()
        assert "overall_status" in d
        assert "rules" in d
        assert len(d["rules"]) == 3
        for rule_d in d["rules"]:
            assert "metric" in rule_d
            assert "operator" in rule_d
            assert "threshold" in rule_d
            assert "actual_value" in rule_d
            assert "status" in rule_d

    def test_spec_example_insufficient_data(self):
        """
        Exact example from specification §9:
        PF=2.1, DD=12%, WR=missing → INSUFFICIENT_DATA
        """
        result = _eval(pf=2.1, dd=12.0)
        assert result.overall_status == "INSUFFICIENT_DATA"
        pf_rule = next(r for r in result.rule_results if r.rule.metric == "profit_factor")
        dd_rule = next(r for r in result.rule_results if r.rule.metric == "equity_drawdown_pct")
        wr_rule = next(r for r in result.rule_results if r.rule.metric == "win_rate")
        assert pf_rule.status == PASS
        assert dd_rule.status == PASS
        assert wr_rule.status == INSUFFICIENT_DATA

    def test_empty_metrics_returns_insufficient_data(self):
        """No metrics at all → INSUFFICIENT_DATA (no FAILs to trigger REJECTED)."""
        result = evaluate_experiment({})
        assert result.overall_status == "INSUFFICIENT_DATA"

    @pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
    @pytest.mark.parametrize("metric", ["profit_factor", "equity_drawdown_pct", "win_rate"])
    def test_non_finite_required_metric_is_insufficient_not_pass_or_fail(self, metric, invalid):
        result = evaluate_experiment({
            "profit_factor": 2.0,
            "equity_drawdown_pct": 10.0,
            "win_rate": 70.0,
            metric: invalid,
        })
        rule = next(item for item in result.rule_results if item.rule.metric == metric)

        assert rule.status == INSUFFICIENT_DATA
        assert rule.actual_value is None
        assert result.overall_status == "INSUFFICIENT_DATA"

    @pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
    @pytest.mark.parametrize("metric", ["profit_factor", "equity_drawdown_pct", "win_rate"])
    def test_non_finite_metric_does_not_override_an_independent_valid_failure(self, metric, invalid):
        metrics = {
            "profit_factor": 2.0,
            "equity_drawdown_pct": 10.0,
            "win_rate": 70.0,
            metric: invalid,
        }
        independent_failure = next(name for name in metrics if name != metric)
        metrics[independent_failure] = {
            "profit_factor": 1.0,
            "equity_drawdown_pct": 30.0,
            "win_rate": 40.0,
        }[independent_failure]

        assert evaluate_experiment(metrics).overall_status == "REJECTED"
