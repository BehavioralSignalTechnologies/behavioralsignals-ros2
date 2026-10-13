from diagnostic_msgs.msg import DiagnosticStatus, KeyValue


class Stats:
    """Counters of one bridge. Consumers derive rates, for example reconnects per hour."""

    def __init__(self):
        self.streams_opened = 0
        self.results = 0
        self.dropped_idle = 0
        self.dropped_full = 0
        self.dropped_format = 0
        self.unsent = 0
        self.queue_high_water = 0
        self.stream_open = False
        self.audio_stalled = False
        self.error = ''
        self.fatal = False

    def note_queue(self, depth):
        self.queue_high_water = max(self.queue_high_water, depth)


def level_and_message(stats, format_problem):
    if format_problem:
        return DiagnosticStatus.ERROR, f'unsupported audio: {format_problem}'
    if stats.fatal:
        return DiagnosticStatus.ERROR, f'stopped, not retrying: {stats.error}'
    if stats.error and not stats.stream_open:
        return DiagnosticStatus.WARN, f'reconnecting after: {stats.error}'
    if stats.audio_stalled:
        return DiagnosticStatus.WARN, 'no audio'
    if not stats.stream_open:
        return DiagnosticStatus.WARN, 'no stream open'
    return DiagnosticStatus.OK, 'streaming'


def status_msg(name, stats, format_problem):
    level, message = level_and_message(stats, format_problem)
    values = [KeyValue(key=k, value=str(v)) for k, v in vars(stats).items()]
    return DiagnosticStatus(level=level, name=name, message=message, values=values)
