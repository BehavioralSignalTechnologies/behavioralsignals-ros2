from setuptools import find_packages, setup

package = 'bsig_ros'

setup(
    name=package,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package]),
        ('share/' + package, ['package.xml']),
        ('share/' + package + '/launch', ['launch/bsig.launch.py']),
        ('share/' + package + '/config', ['config/bsig.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Behavioral Signals',
    maintainer_email='api-support@behavioralsignals.com',
    description='Behavioral Signals streaming API bridge for ROS 2',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'bsig_bridge = bsig_ros.bridge:main',
            'bsig_affect = bsig_ros.affect:main',
        ],
    },
)
