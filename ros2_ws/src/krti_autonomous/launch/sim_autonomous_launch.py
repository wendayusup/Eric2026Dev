import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    package_dir = get_package_share_directory('krti_autonomous')
    rviz_config_path = os.path.join(package_dir, 'rviz', 'krti_view.rviz')

    # ==========================================================
    # LAUNCH ARGUMENTS (opsional, bisa di-pass saat launch)
    # Contoh: ros2 launch krti_autonomous sim_autonomous_launch.py launch_rviz:=true
    # ==========================================================
    launch_rviz_arg = DeclareLaunchArgument(
        'launch_rviz',
        default_value='false',
        description='Jalankan RViz2 (true/false). Default: false untuk menghemat CPU/GPU.'
    )
    launch_visual_servo_arg = DeclareLaunchArgument(
        'launch_visual_servo',
        default_value='true',
        description='Jalankan node visual servo otonom (true/false). Default: true.'
    )

    launch_rviz = LaunchConfiguration('launch_rviz')
    launch_visual_servo = LaunchConfiguration('launch_visual_servo')

    # ==========================================================
    # Node GCS Bridge (Flask server + Socket.IO + telemetri)
    # ==========================================================
    gcs_bridge_node = Node(
        package='krti_autonomous',
        executable='gcs_bridge_node',
        parameters=[{'use_sim_time': False}],  # Web server tidak perlu sim time
        output='screen'
    )

    # ==========================================================
    # Node Visual Servo / Autonomous controller (opsional)
    # ==========================================================
    visual_servo_node = Node(
        package='krti_autonomous',
        executable='visual_servo_node',
        parameters=[{'use_sim_time': True}],
        output='screen',
        condition=IfCondition(launch_visual_servo)
    )

    # ==========================================================
    # Jembatan Gazebo → ROS2 (ros_gz_image) untuk Dual Camera
    # Model: iris_dual_cam di world iris_runway
    # ==========================================================
    gz_bridge_node = Node(
        package='ros_gz_image',
        executable='image_bridge',
        arguments=[
            '/world/iris_runway/model/iris_dual_cam/link/front_camera_link/sensor/front_camera/image',
            '/world/iris_runway/model/iris_dual_cam/link/down_camera_link/sensor/down_camera/image'
        ],
        remappings=[
            ('/world/iris_runway/model/iris_dual_cam/link/front_camera_link/sensor/front_camera/image', '/camera/front'),
            ('/world/iris_runway/model/iris_dual_cam/link/down_camera_link/sensor/down_camera/image', '/camera/bottom')
        ],
        output='screen'
    )

    # ==========================================================
    # Node MAVROS untuk ArduPilot SITL (UDP)
    # ==========================================================
    fcu_url_arg = DeclareLaunchArgument(
        'fcu_url',
        default_value='udp://127.0.0.1:14550@',
        description='URL ke flight controller (SITL). Default: udp://127.0.0.1:14550@'
    )
    fcu_url = LaunchConfiguration('fcu_url')

    mavros_config_file = os.path.join(get_package_share_directory('mavros'), 'launch', 'apm_config.yaml')
    mavros_pluginlists_file = os.path.join(get_package_share_directory('mavros'), 'launch', 'apm_pluginlists.yaml')

    mavros_node = Node(
        package='mavros',
        executable='mavros_node',
        output='screen',
        parameters=[
            mavros_pluginlists_file,
            mavros_config_file,
            {'fcu_url': fcu_url},
            {'gcs_url': ''},
            {'target_system_id': 1},
            {'target_component_id': 1},
            {'fcu_protocol': 'v2.0'},
            {'conn/timeout': 60.0},
            {'conn/heartbeat_rate': 1.0}
        ]
    )

    # ==========================================================
    # Visualisasi RViz2 (OPSIONAL — default: OFF)
    # Aktifkan dengan: launch_rviz:=true
    # ==========================================================
    rviz2_node = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', rviz_config_path] if os.path.exists(rviz_config_path) else [],
        output='screen',
        condition=IfCondition(launch_rviz)
    )

    return LaunchDescription([
        launch_rviz_arg,
        launch_visual_servo_arg,
        fcu_url_arg,
        mavros_node,
        gz_bridge_node,
        gcs_bridge_node,
        visual_servo_node,
        rviz2_node,
    ])
