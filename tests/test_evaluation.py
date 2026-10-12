import numpy as np
import pandas as pd
import pytest

from apex_rca.evaluation import (
    apply_holm_correction,
    case_metrics,
    compare_method_dataframes,
    hit_at_k,
    holm_bonferroni,
    mcnemar_exact,
    paired_bootstrap_delta_ci,
    paired_metric_comparison,
    reciprocal_rank,
)


def test_hit_at_k_and_mrr():
    ranked = ["a", "b", "c", "d", "e"]
    assert hit_at_k(ranked, "a", 1) == 1
    assert hit_at_k(ranked, "c", 1) == 0
    assert hit_at_k(ranked, "c", 3) == 1
    assert hit_at_k(ranked, "e", 5) == 1
    assert reciprocal_rank(ranked, "c") == 1 / 3
    assert case_metrics(ranked, "b")["rank"] == 2


def test_missing_truth_is_not_a_hit():
    assert hit_at_k(["a"], "", 1) == 0
    assert reciprocal_rank(["a"], "") == 0.0


def test_mcnemar_detects_discordance():
    a = [1, 1, 0, 0, 1]
    b = [1, 0, 1, 0, 1]
    result = mcnemar_exact(a, b)
    assert result["a_correct_b_wrong"] == 1
    assert result["a_wrong_b_correct"] == 1
    assert result["n_paired"] == 5


def test_paired_bootstrap_delta_is_b_minus_a():
    mean, low, high, n = paired_bootstrap_delta_ci(
        [0.0, 0.0, 1.0, 1.0],
        [1.0, 1.0, 1.0, 1.0],
        n_boot=500,
        seed=7,
    )
    assert n == 4
    assert mean == 0.5
    assert low <= mean <= high


def test_paired_bootstrap_drops_nonfinite_pairs():
    result = paired_bootstrap_delta_ci(
        [0.0, np.nan, 1.0],
        [1.0, 1.0, np.inf],
    )
    assert result[3] == 1
    assert result[0] == 1.0


def test_paired_metric_comparison_uses_mcnemar_for_hit():
    result = paired_metric_comparison(
        [1, 0, 0, 1],
        [1, 1, 0, 0],
        metric="hit1",
    )
    assert result["test"] == "mcnemar_exact"
    assert result["n_paired"] == 4
    assert result["a_correct_b_wrong"] == 1
    assert result["a_wrong_b_correct"] == 1


def test_paired_metric_comparison_uses_wilcoxon_for_mrr():
    result = paired_metric_comparison(
        [0.25, 0.5, 1.0, 0.0],
        [0.5, 0.5, 1.0, 0.25],
        metric="mrr",
    )
    assert result["test"] == "wilcoxon_signed_rank"
    assert result["n_paired"] == 4
    assert 0.0 <= result["pvalue"] <= 1.0


def test_holm_correction_preserves_original_order():
    results = apply_holm_correction(
        [{"pvalue": 0.01}, {"pvalue": 0.2}, {"pvalue": 0.02}]
    )
    assert [item["pvalue_holm"] for item in results] == pytest.approx(
        [0.03, 0.2, 0.04]
    )


def test_mcnemar_exact_known_proportions():
    # 39 wins for B, 10 losses for B, 684 ties (identical to RCAEval graph vs baseline)
    a = [0] * 39 + [1] * 10 + [1] * 500 + [0] * 184
    b = [1] * 39 + [0] * 10 + [1] * 500 + [0] * 184
    res = mcnemar_exact(a, b)
    assert res["n_paired"] == 733
    assert res["wins"] == 39
    assert res["losses"] == 10
    assert res["ties"] == 684
    assert res["odds_ratio"] == pytest.approx(3.9)
    assert res["pvalue"] == pytest.approx(3.8459e-05, rel=1e-3)
    assert res["risk_difference"] == pytest.approx((39 - 10) / 733)

    # All concordant: p-value must be 1.0
    res_ties = mcnemar_exact([1, 0, 1], [1, 0, 1])
    assert res_ties["pvalue"] == 1.0
    assert res_ties["ties"] == 3
    assert res_ties["wins"] == 0
    assert res_ties["losses"] == 0

    # Zero losses: 4 wins, 0 losses -> binomtest(4, 4, 0.5) two-sided = 2 * (0.5)^4 = 0.125
    res_zero_loss = mcnemar_exact([0, 0, 0, 0], [1, 1, 1, 1])
    assert res_zero_loss["wins"] == 4
    assert res_zero_loss["losses"] == 0
    assert res_zero_loss["pvalue"] == pytest.approx(0.125)
    assert np.isinf(res_zero_loss["odds_ratio"])
    assert res_zero_loss["haldane_odds_ratio"] == pytest.approx(9.0)


def test_wilcoxon_known_effect_sizes():
    # All positive differences -> rank_biserial_r must be +1.0
    a = [0.1, 0.2, 0.3, 0.4]
    b = [0.3, 0.5, 0.7, 0.9]
    res_pos = paired_metric_comparison(a, b, metric="mrr")
    assert res_pos["wins"] == 4
    assert res_pos["losses"] == 0
    assert res_pos["ties"] == 0
    assert res_pos["rank_biserial_r"] == pytest.approx(1.0)
    assert res_pos["cohen_dz"] > 0

    # All negative differences -> rank_biserial_r must be -1.0
    res_neg = paired_metric_comparison(b, a, metric="mrr")
    assert res_neg["wins"] == 0
    assert res_neg["losses"] == 4
    assert res_neg["ties"] == 0
    assert res_neg["rank_biserial_r"] == pytest.approx(-1.0)
    assert res_neg["cohen_dz"] < 0

    # Identical pairs -> ties, pvalue=1.0, rank_biserial_r=0.0
    res_ident = paired_metric_comparison([0.5, 0.5], [0.5, 0.5], metric="mrr")
    assert res_ident["ties"] == 2
    assert res_ident["wins"] == 0
    assert res_ident["losses"] == 0
    assert res_ident["pvalue"] == 1.0
    assert res_ident["rank_biserial_r"] == pytest.approx(0.0)


def test_paired_bootstrap_constant_difference():
    # When all differences are equal to 0.5, any bootstrap sample has mean 0.5
    mean, low, high, n = paired_bootstrap_delta_ci(
        [0.1, 0.2, 0.3, 0.4],
        [0.6, 0.7, 0.8, 0.9],
        n_boot=100,
        seed=1,
    )
    assert n == 4
    assert mean == pytest.approx(0.5)
    assert low == pytest.approx(0.5)
    assert high == pytest.approx(0.5)


def test_compare_method_dataframes_known_pairs_and_missing():
    df_a = pd.DataFrame(
        {
            "case": ["c1", "c2", "c3"],
            "hit1": [1, 0, 1],
            "hit3": [1, 1, 1],
            "hit5": [1, 1, 1],
            "mrr": [1.0, 0.5, 1.0],
        }
    )
    df_b = pd.DataFrame(
        {
            "case": ["c2", "c3", "c4"],
            "hit1": [1, 1, 0],
            "hit3": [1, 1, 1],
            "hit5": [1, 1, 1],
            "mrr": [1.0, 1.0, 0.33],
        }
    )
    res = compare_method_dataframes(df_a, df_b, label_a="A", label_b="B")
    assert res["n_a"] == 3
    assert res["n_b"] == 3
    assert res["n_intersection"] == 2
    assert res["n_missing_in_a"] == 1
    assert res["missing_in_a"] == ["c4"]
    assert res["n_missing_in_b"] == 1
    assert res["missing_in_b"] == ["c1"]
    assert len(res["comparisons"]) == 4  # hit1, hit3, hit5, mrr
    assert len(res["comparisons_holm"]) == 4

    # Duplicate case check
    dup_df = pd.DataFrame({"case": ["c1", "c1"], "hit1": [1, 0]})
    with pytest.raises(ValueError, match="Duplicate cases"):
        compare_method_dataframes(dup_df, df_b)


def test_holm_bonferroni_known_correction():
    # 4 hypothesis tests with known p-values
    pvals = [0.005, 0.04, 0.01, 0.02]
    # Sorted:
    # rank 0: 0.005 * 4 = 0.02
    # rank 1: 0.01 * 3 = 0.03
    # rank 2: 0.02 * 2 = 0.04
    # rank 3: 0.04 * 1 = 0.04
    # In original order: [0.02, 0.04, 0.03, 0.04]
    adj = holm_bonferroni(pvals)
    assert adj == pytest.approx([0.02, 0.04, 0.03, 0.04])

