import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    package_dir = get_package_share_directory('krti_autonomous')

    # ==========================================================
    # LAUNCH ARGUMENTS
    # ==========================================================
    fcu_url_arg = DeclareLaunchArgument(
        'fcu_url',
        default_value='/dev/ttyUSB0:57600',
        description='URL ke flight controller (serial port). Contoh: /dev/ttyUSB0:57600'
    )
    
    gcs_url_arg = DeclareLaunchArgument(
        'gcs_url',
        default_value='',
        description='URL ke GCS (misal QGroundControl via UDP)'
    )

    launch_visual_servo_arg = DeclareLaunchArgument(
        'launch_visual_servo',
        default_value='false',
        description='Jalankan node visual servo otonom (true/false). Default: false.'
    )

    launch_rviz_arg = DeclareLaunchArgument(
        'launch_rviz',
        default_value='true',
        description='Jalankan RViz2 (true/false). Default: true.'
    )

    fcu_url = LaunchConfiguration('fcu_url')
    gcs_url = LaunchConfiguration('gcs_url')
    launch_visual_servo = LaunchConfiguration('launch_visual_servo')
    launch_rviz = LaunchConfiguration('launch_rviz')

    # ==========================================================
    # Node MAVROS
    # ==========================================================
    mavros_node = Node(
        package='mavros',
        executable='mavros_node',
        output='screen',
        parameters=[
            {'fcu_url': fcu_url},
            {'gcs_url': gcs_url},
            {'target_system_id': 1},
            {'target_component_id': 1},
            {'fcu_protocol': 'v2.0'},
            {'conn/timeout': 60.0},
            {'conn/heartbeat_rate': 1.0}
        ]
    )

    # ==========================================================
    # Node GCS Bridge (Flask server + Socket.IO + telemetri)
    # ==========================================================
    gcs_bridge_node = Node(
        package='krti_autonomous',
        executable='gcs_bridge_node',
        parameters=[{'use_sim_time': False}],
        output='screen'
    )

    # ==========================================================
    # Node Visual Servo / Autonomous controller
    # ==========================================================
    visual_servo_node = Node(
        package='krti_autonomous',
        executable='visual_servo_node',
        parameters=[{'use_sim_time': False}],
        output='screen',
        condition=IfCondition(launch_visual_servo)
    )

    # ==========================================================
    # Visualisasi RViz2 (OPSIONAL)
    # ==========================================================
    rviz_config_path = os.path.join(package_dir, 'rviz', 'krti_view.rviz')
    rviz2_node = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', rviz_config_path] if os.path.exists(rviz_config_path) else [],
        output='screen',
        condition=IfCondition(launch_rviz)
    )

    return LaunchDescription([
        fcu_url_arg,
        gcs_url_arg,
        launch_visual_servo_arg,
        launch_rviz_arg,
        mavros_node,
        gcs_bridge_node,
        visual_servo_node,
        rviz2_node
    ])
