"""Writes the results bag as two plain CSV files.

Usage: python3 results_to_csv.py <results_bag_dir> <output_prefix>
Writes <output_prefix>_api_results.csv (one row per label, or per value for tasks without labels),
<output_prefix>_affect.csv and, when the bag has deepfake results, <output_prefix>_deepfake.csv.
"""
import csv
import math
import sys

from summarize_results import AUDIO_T0, affect_time, read_bag, result_rows, seconds

API_COLUMNS = ['window_start_s', 'window_end_s', 'level', 'task', 'final_label', 'label', 'confidence', 'logit', 'score']
AFFECT_COLUMNS = ['time_s', 'emotion', 'emotion_confidence', 'valence', 'arousal']


def api_rows(results):
    for _, msg in results:
        for i in msg.results:
            for p in i.predictions:
                if not p.label and math.isnan(p.score):
                    continue
                yield [round(seconds(i.start) - AUDIO_T0, 2), round(seconds(i.end) - AUDIO_T0, 2), i.level, i.task,
                       i.final_label, p.label, round(p.posterior, 4), round(p.logit, 4), round(p.score, 4)]


def affect_rows(results, affects):
    first_received = results[0][0]
    first_end = max(r[1] for r in result_rows(results[0][1]))
    for received, a in affects:
        yield [round(affect_time(received, first_received, first_end), 2), a.emotion, round(a.emotion_posterior, 4),
               round(a.valence, 4), round(a.arousal, 4)]


def write_csv(path, columns, rows):
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)


def main(bag, prefix):
    results, affects, deepfakes = read_bag(bag)
    write_csv(f'{prefix}_api_results.csv', API_COLUMNS, sorted(api_rows(results), key=lambda r: (r[0], r[2], r[3])))
    write_csv(f'{prefix}_affect.csv', AFFECT_COLUMNS, affect_rows(results, affects))
    if deepfakes:
        write_csv(f'{prefix}_deepfake.csv', API_COLUMNS, sorted(api_rows(deepfakes), key=lambda r: (r[0], r[2], r[3])))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
