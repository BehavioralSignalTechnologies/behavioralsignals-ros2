"""Writes a 16-bit mono WAV file to a rosbag with /audio_info and /audio_stamped.

Usage: python3 wav_to_bag.py <audio.wav> <bag_dir>
Audio is cut into 250 ms messages. Stamps start at 1760000000 s (summarize_results.py relies on it).
"""
import sys
import wave

import rosbag2_py
from audio_common_msgs.msg import AudioDataStamped, AudioInfo
from rclpy.serialization import serialize_message
from rosbag2_py._storage import QoS

T0_NS = 1_760_000_000 * 10**9
MESSAGE_NS = 250_000_000


def read_wav(path):
    with wave.open(path, 'rb') as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2, 'need mono 16-bit audio'
        return w.getframerate(), w.readframes(w.getnframes())


def open_writer(path):
    writer = rosbag2_py.SequentialWriter()
    writer.open(rosbag2_py.StorageOptions(uri=path, storage_id='mcap'), rosbag2_py.ConverterOptions('', ''))
    latched = [QoS(1).reliable().transient_local()]
    writer.create_topic(rosbag2_py.TopicMetadata(
        id=0, name='/audio_info', type='audio_common_msgs/msg/AudioInfo',
        serialization_format='cdr', offered_qos_profiles=latched))
    writer.create_topic(rosbag2_py.TopicMetadata(
        id=1, name='/audio_stamped', type='audio_common_msgs/msg/AudioDataStamped', serialization_format='cdr'))
    return writer


def audio_info(rate):
    return AudioInfo(channels=1, sample_rate=rate, sample_format='S16LE', bitrate=0, coding_format='wave')


def audio_message(stamp_ns, data):
    msg = AudioDataStamped()
    msg.header.stamp.sec, msg.header.stamp.nanosec = divmod(stamp_ns, 10**9)
    msg.audio.data = data
    return msg


def main(wav, out):
    rate, pcm = read_wav(wav)
    writer = open_writer(out)
    writer.write('/audio_info', serialize_message(audio_info(rate)), T0_NS)
    step = rate // 4 * 2
    for n, i in enumerate(range(0, len(pcm), step)):
        stamp = T0_NS + n * MESSAGE_NS
        writer.write('/audio_stamped', serialize_message(audio_message(stamp, pcm[i:i + step])), stamp)


if __name__ == '__main__':
    main(*sys.argv[1:3])
