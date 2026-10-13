import math

SIGNED_TASKS = {
    'positivity': ('positive', 'negative'),
    'strength': ('strong', 'weak'),
}


def signed_score(predictions, pos, neg):
    p = {x.label: x.posterior for x in predictions if not math.isnan(x.posterior)}
    return p.get(pos, 0.0) - p.get(neg, 0.0)


def top_posterior(predictions):
    return max((p.posterior for p in predictions if not math.isnan(p.posterior)), default=math.nan)


class AffectTracker:
    """Smooths segment results into steady valence and arousal scores."""

    def __init__(self, tau):
        if tau <= 0:
            raise ValueError(f'time_constant_s must be positive, got {tau!r}')
        self.tau = tau
        self.values = {}
        self.last = {}
        self.emotion = ''
        self.emotion_posterior = math.nan

    def update(self, r, t):
        """Returns True when the result changed the tracked state."""
        if r.level != 'segment':
            return False
        if r.task in SIGNED_TASKS:
            self._smooth(r.task, signed_score(r.predictions, *SIGNED_TASKS[r.task]), t)
        elif r.task == 'emotion':
            self.emotion = r.final_label
            self.emotion_posterior = top_posterior(r.predictions)
        else:
            return False
        return True

    def ready(self):
        return all(k in self.values for k in SIGNED_TASKS)

    def _smooth(self, key, x, t):
        if key in self.values:
            a = 1.0 - math.exp(-max(t - self.last[key], 0.0) / self.tau)
            x = self.values[key] + a * (x - self.values[key])
        self.values[key] = x
        self.last[key] = t
