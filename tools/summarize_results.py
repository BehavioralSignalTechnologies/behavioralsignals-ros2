"""Prints a timeline of the results bag written by replay.sh.

Usage: python3 summarize_results.py <results_bag_dir>
Times are seconds from the start of the audio (the bag from wav_to_bag.py starts at 1760000000 s).
"""
import collections
import sys

import rosbag2_py
from bsig_msgs.msg import Affect, StreamResult
from rclpy.serialization import deserialize_message

AUDIO_T0 = 1_760_000_000.0
TASKS = ('emotion', 'positivity', 'strength', 'gender')
TYPES = {'/bsig/results': StreamResult, '/bsig/affect': Affect, '/bsig/deepfake': StreamResult}


def read_bag(path):
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=path, storage_id='mcap'), rosbag2_py.ConverterOptions('', ''))
    messages = collections.defaultdict(list)
    while reader.has_next():
        topic, data, t = reader.read_next()
        if topic in TYPES:
            messages[topic].append((t / 1e9, deserialize_message(data, TYPES[topic])))
    if not messages['/bsig/results']:
        sys.exit(f'no results in {path}; check the bridge log or /diagnostics')
    return messages['/bsig/results'], messages['/bsig/affect'], messages['/bsig/deepfake']


def seconds(stamp):
    return stamp.sec + stamp.nanosec / 1e9


EXPLANATION = """How to read this file
-------------------
Part 1 lists what the API returned. Each line is one window of audio. The times are seconds from the start of the audio.
  level      segment = short window of about 2 s. utterance = a whole phrase; these arrive late and cover earlier time.
  columns    the label the API ranked first for that task, with its confidence (0 to 1) in brackets.
             A low confidence (below about 0.7) means the label is weak.
Part 2 lists the smoothed result made by our bsig_affect node. It is not API output.
  valence -1 (negative) to +1 (positive).   arousal -1 (weak) to +1 (strong).   confidence: of the emotion label.
  Valence is made from the API's positivity task. Arousal is made from the API's strength task.
  The time is when the message arrived, lined up with the first result, so it is approximate.
Part 3 lists what the API's deepfake detection returned: bonafide (real speech) or spoofed (fake speech), with its confidence.
"""


def top_labels(results, tasks=TASKS):
    top = {}
    for i in results:
        if i.task in tasks:
            best = max(i.predictions, key=lambda p: p.posterior)
            top[i.task] = f'{best.label} ({best.posterior:.2f})'
    return top


def result_rows(msg, tasks=TASKS):
    by_level = collections.defaultdict(list)
    for i in msg.results:
        by_level[i.level].append(i)
    for level, items in by_level.items():
        start = min(seconds(i.start) for i in items) - AUDIO_T0
        end = max(seconds(i.end) for i in items) - AUDIO_T0
        yield start, end, level, top_labels(items, tasks)


def print_results(results):
    rows = sorted(r for _, msg in results for r in result_rows(msg))
    print(f'Part 1: API results, {len(rows)} windows covering 0 to {max(r[1] for r in rows):.0f} s of audio')
    print(f'{"window (s)":>14}  {"level":9}' + ''.join(f'  {t:18}' for t in TASKS))
    for start, end, level, top in rows:
        print(f'{start:6.1f} - {end:5.1f}  {level:9}' + ''.join(f'  {top.get(t, "-"):18}' for t in TASKS))


def affect_time(received, first_received, first_end):
    return received - first_received + first_end


def print_affect(affects, first_received, first_end):
    print(f'\nPart 2: smoothed affect from bsig_affect, {len(affects)} messages')
    print(f'{"time (s)":>8}  {"emotion":8}  {"valence":>8}  {"arousal":>8}  {"confidence":>10}')
    for received, a in affects:
        t = affect_time(received, first_received, first_end)
        print(f'{t:8.1f}  {a.emotion:8}  {a.valence:+8.2f}  {a.arousal:+8.2f}  {a.emotion_posterior:10.2f}')


def print_deepfake(deepfakes):
    print(f'\nPart 3: deepfake detection from the API, {len(deepfakes)} messages')
    print(f'{"window (s)":>14}  {"level":9}  {"deepfake":18}')
    for start, end, level, top in sorted(r for _, msg in deepfakes for r in result_rows(msg, ('deepfake',))):
        print(f'{start:6.1f} - {end:5.1f}  {level:9}  {top.get("deepfake", "-"):18}')


def main(path):
    results, affects, deepfakes = read_bag(path)
    print(EXPLANATION)
    print_results(results)
    first_end = max(r[1] for r in result_rows(results[0][1]))
    print_affect(affects, results[0][0], first_end)
    if deepfakes:
        print_deepfake(deepfakes)


if __name__ == '__main__':
    main(sys.argv[1])
