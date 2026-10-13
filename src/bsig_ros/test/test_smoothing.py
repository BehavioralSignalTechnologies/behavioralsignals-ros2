import math
from types import SimpleNamespace as N

import pytest

from bsig_ros.smoothing import AffectTracker, signed_score, top_posterior


def preds(**posteriors):
    return [N(label=k, posterior=v) for k, v in posteriors.items()]


def result(task, level='segment', final_label='', **posteriors):
    return N(task=task, level=level, final_label=final_label, predictions=preds(**posteriors))


def test_signed_score_is_positive_minus_negative():
    assert signed_score(preds(positive=0.7, negative=0.1, neutral=0.2), 'positive', 'negative') == pytest.approx(0.6)


def test_signed_score_missing_label_counts_as_zero():
    assert signed_score(preds(positive=0.5), 'positive', 'negative') == 0.5


def test_not_ready_until_both_scores_seen():
    t = AffectTracker(tau=3.0)
    t.update(result('positivity', positive=1.0, negative=0.0), 2.0)
    assert not t.ready()
    t.update(result('strength', strong=1.0, weak=0.0), 2.0)
    assert t.ready()


def test_signals_sharing_a_timestamp_all_advance():
    t = AffectTracker(tau=3.0)
    t.update(result('positivity', positive=0.0, negative=0.0), 2.0)
    t.update(result('strength', strong=0.0, weak=0.0), 2.0)
    t.update(result('positivity', positive=1.0, negative=0.0), 4.0)
    t.update(result('strength', strong=1.0, weak=0.0), 4.0)
    expected = 1.0 - math.exp(-2.0 / 3.0)
    assert math.isclose(t.values['positivity'], expected)
    assert math.isclose(t.values['strength'], expected)


def test_utterance_results_are_ignored():
    t = AffectTracker(tau=3.0)
    assert not t.update(result('positivity', level='utterance', positive=1.0), 2.0)
    assert t.values == {}


def test_emotion_keeps_label_and_top_posterior():
    t = AffectTracker(tau=3.0)
    assert t.update(result('emotion', final_label='happy', happy=0.8, sad=0.2), 2.0)
    assert t.emotion == 'happy'
    assert t.emotion_posterior == 0.8


def test_unrelated_task_changes_nothing():
    t = AffectTracker(tau=3.0)
    assert not t.update(result('age', final_label='23 - 30', **{'23 - 30': 0.9}), 2.0)


def test_time_constant_must_be_positive():
    with pytest.raises(ValueError):
        AffectTracker(0)


def test_missing_posterior_does_not_poison_the_score():
    predictions = [N(label='positive', posterior=math.nan), N(label='negative', posterior=0.25)]
    assert signed_score(predictions, 'positive', 'negative') == -0.25


def test_top_posterior_ignores_missing_values():
    assert top_posterior([N(label='a', posterior=math.nan), N(label='b', posterior=0.4)]) == 0.4
