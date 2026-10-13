import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    config = os.path.join(get_package_share_directory('bsig_ros'), 'config', 'bsig.yaml')
    ns = LaunchConfiguration('namespace')
    sim_time = {'use_sim_time': ParameterValue(LaunchConfiguration('use_sim_time'), value_type=bool)}
    return LaunchDescription([
        DeclareLaunchArgument('namespace', default_value='mic1'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        Node(package='bsig_ros', executable='bsig_bridge', name='bsig_behavior', namespace=ns,
             parameters=[config, sim_time, {'method': 'StreamAudio'}]),
        Node(package='bsig_ros', executable='bsig_bridge', name='bsig_deepfake', namespace=ns,
             parameters=[config, sim_time, {'method': 'DeepfakeDetection'}],
             remappings=[('bsig/results', 'bsig/deepfake')]),
        Node(package='bsig_ros', executable='bsig_affect', name='bsig_affect', namespace=ns,
             parameters=[config, sim_time]),
    ])
