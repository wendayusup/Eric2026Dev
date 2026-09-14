from setuptools import find_packages, setup

package_name = 'krti_autonomous'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', [
            'launch/sim_autonomous_launch.py',
            'launch/real_drone_launch.py',
            'launch/ardupilot_launch.py'
        ]),
        ('share/' + package_name + '/rviz', ['rviz/krti_view.rviz']),
        ('share/' + package_name + '/config', ['config/apm_config.yaml', 'config/apm_pluginlists.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='wenda',
    maintainer_email='wendayusup739@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'gcs_bridge_node = krti_autonomous.gcs_bridge_node:main',
            'real_gcs_bridge_node = krti_autonomous.real_gcs_bridge_node:main',
            'visual_servo_node = krti_autonomous.visual_servo_node:main',
        ],
    },
)
