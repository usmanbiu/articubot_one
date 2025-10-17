import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, RegisterEventHandler, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PythonExpression
from launch.event_handlers import OnProcessExit
from launch_ros.actions import Node
from launch.conditions import IfCondition, UnlessCondition


def generate_launch_description():
    # delare any path variable
    pkg_path = get_package_share_directory('articubot_one')
    #base_pkg_path = get_package_share_directory('demo_bot_base')

    # Launch configuration variables specific to simulation
    use_ekf = LaunchConfiguration('use_ekf')

    declare_use_ekf_cmd = DeclareLaunchArgument(
      name='use_ekf',
      default_value='True',
      description='fuse odometry and imu data if true')
    
    # create needed nodes or launch files
    rsp_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(pkg_path,'launch','rsp.launch.py')]), 
        launch_arguments={'use_sim_time': 'False',
                          'use_joint_state_pub': 'False'}.items())
    

    robot_controllers = os.path.join(pkg_path,'config','robot_base_controller.yaml')

    # see -> https://github.com/ros-controls/ros2_control_demos/blob/humble/example_2/bringup/launch/diffbot.launch.py
    # see -> https://control.ros.org/master/doc/ros2_control/controller_manager/doc/userdoc.html
    controller_manager = Node(
        package="controller_manager",
        executable="ros2_control_node",
        parameters=[robot_controllers],
        output="both",
    )

    joint_state_broadcaster_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["joint_state_broadcaster"],
    )

    diff_drive_controller_spawner_no_ekf = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "diff_drive_controller",
            "--param-file",
            robot_controllers,
            "--controller-ros-args",
            """
            -r /diff_drive_controller/cmd_vel:=/cmd_vel
            -r /diff_drive_controller/odom:=/odom
            """
        ],
        condition=UnlessCondition(use_ekf),
    )

    diff_drive_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "diff_drive_controller",
            "--param-file",
            robot_controllers,
            "--controller-ros-args",
            """
            -r /diff_drive_controller/cmd_vel:=/cmd_vel
            -r /diff_drive_controller/odom:=/wheel/odometry
            """
        ],
        condition=IfCondition(use_ekf),
    )

    eimu_ros_config_file = os.path.join(pkg_path,'config','eimu_params.yaml')
    eimu_ros_node = Node(
        package='eimu_ros',
        executable='eimu_ros',
        name='eimu_ros',
        output='screen',
        parameters=[
            eimu_ros_config_file
        ],
        condition=IfCondition(use_ekf)
    )

    ekf_config_path = os.path.join(pkg_path,'config','ekf.yaml')
    ekf_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        parameters=[
            ekf_config_path
        ],
        condition=IfCondition(use_ekf),
        remappings=[("odometry/filtered", "/odom")]
    ) 

    # Delay start of robot_controller after `joint_state_broadcaster`
    start_diff_drive_controller_spawner_after_joint_state_broadcaster_spawner = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=joint_state_broadcaster_spawner,
            on_exit=[diff_drive_controller_spawner],
        )
    )

    start_diff_drive_controller_spawner_after_joint_state_broadcaster_spawner_no_ekf = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=joint_state_broadcaster_spawner,
            on_exit=[diff_drive_controller_spawner_no_ekf],
        )
    )

    # start_imu_broadcaster_spawner_after_diff_drive_controller_spawner = RegisterEventHandler(
    #     event_handler=OnProcessExit(
    #         target_action=diff_drive_controller_spawner,
    #         on_exit=[eimu_ros_node],
    #     )
    # )

    # start_ekf_node_after_imu_broadcaster_spawner = RegisterEventHandler(
    #     event_handler=OnProcessExit(
    #         target_action=imu_broadcaster_spawner,
    #         on_exit=[ekf_node],
    #     )
    # )

    # Create the launch description and populate
    ld = LaunchDescription()

    # add the necessary declared launch arguments to the launch description
    ld.add_action(declare_use_ekf_cmd)

    # Add the nodes to the launch description
    ld.add_action(rsp_launch)
    ld.add_action(controller_manager)
    ld.add_action(joint_state_broadcaster_spawner)
    ld.add_action(start_diff_drive_controller_spawner_after_joint_state_broadcaster_spawner)
    ld.add_action(start_diff_drive_controller_spawner_after_joint_state_broadcaster_spawner_no_ekf)
    # ld.add_action(start_imu_broadcaster_spawner_after_diff_drive_controller_spawner)
    # ld.add_action(start_ekf_node_after_imu_broadcaster_spawner)
    ld.add_action(eimu_ros_node)
    ld.add_action(ekf_node)

    return ld      # return (i.e send) the launch description for excecution