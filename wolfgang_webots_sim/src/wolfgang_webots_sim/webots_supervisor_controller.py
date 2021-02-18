from controller import Robot, Node, Supervisor, Field

import os
import rospy
from geometry_msgs.msg import Quaternion, PointStamped
from sensor_msgs.msg import JointState, Imu, Image, CameraInfo

from rosgraph_msgs.msg import Clock
from std_srvs.srv import Empty

from bitbots_msgs.msg import JointCommand, FootPressure
import math
import transforms3d
import numpy as np

G = 9.81


class SupervisorController:
    def __init__(self, ros_active=False, mode='normal'):
        # requires WEBOTS_ROBOT_NAME to be set to "amy" or "rory"
        self.ros_active = ros_active
        self.time = 0
        self.clock_msg = Clock()

        self.supervisor = Supervisor()
        self.amy_node = self.supervisor.getFromDef("amy")
        self.rory_node = self.supervisor.getFromDef("rory")
        self.jack_node = self.supervisor.getFromDef("jack")
        self.donna_node = self.supervisor.getFromDef("donna")
        self.melody_node = self.supervisor.getFromDef("melody")

        if mode == 'normal':
            self.supervisor.simulationSetMode(Supervisor.SIMULATION_MODE_REAL_TIME)
        elif mode == 'paused':
            self.supervisor.simulationSetMode(Supervisor.SIMULATION_MODE_PAUSE)
        elif mode == 'run':
            self.supervisor.simulationSetMode(Supervisor.SIMULATION_MODE_RUN)
        elif mode == 'fast':
            self.supervisor.simulationSetMode(Supervisor.SIMULATION_MODE_FAST)
        else:
            self.supervisor.simulationSetMode(Supervisor.SIMULATION_MODE_REAL_TIME)

        self.motors = []
        self.sensors = []
        self.timestep = int(self.supervisor.getBasicTimeStep())

        # resolve the node for corresponding name
        self.robot_names = ["amy", "rory", "jack", "donna", "melody"]
        self.robot_nodes = {}
        self.translation_fields = {}
        self.rotation_fields = {}

        # check if None
        for name in self.robot_names:
            self.robot_nodes[name] = self.supervisor.getFromDef(name)
            if self.robot_nodes[name] is not None:
                self.translation_fields[name] = self.robot_nodes[name].getField("translation")
                self.rotation_fields[name] = self.robot_nodes[name].getField("rotation")

        if self.ros_active:
            rospy.init_node("webots_ros_supervisor", anonymous=True,
                            argv=['clock:=/clock'])
            self.clock_publisher = rospy.Publisher("/clock", Clock, queue_size=1)
            self.reset_service = rospy.Service("reset", Empty, self.reset)

        self.world_info = self.supervisor.getFromDef("world_info")

    def step_sim(self):
        self.time += self.timestep / 1000
        self.supervisor.step(self.timestep)

    def step(self):
        self.step_sim()
        if self.ros_active:
            self.publish_clock()

    def publish_clock(self):
        self.clock_msg.clock = rospy.Time.from_seconds(self.time)
        self.clock_publisher.publish(self.clock_msg)

    def set_gravity(self, active):
        if active:
            self.world_info.getField("gravity").setSFVec3f([0.0, -9.81, 0.0])
            self.world_info.getField("gravity").setSFFloat(9.81)
        else:
            self.world_info.getField("gravity").setSFVec3f([0.0, 0.0, 0.0])
            self.world_info.getField("gravity").setSFFloat(0)

    def reset_robot_pose(self, pos, quat, name="amy"):
        self.set_robot_pose_quat(pos, quat)
        if name in self.robot_nodes:
            self.robot_nodes[name].resetPhysics()

    def reset_robot_pose_rpy(self, pos, rpy, name="amy"):
        self.set_robot_pose_rpy(pos, rpy)
        if name in self.robot_nodes:
            self.robot_nodes[name].resetPhysics()

    def reset(self, req=None):
        self.supervisor.simulationReset()
        self.supervisor.simulationResetPhysics()

    def node(self):
        s = self.supervisor.getSelected()
        if s is not None:
            print(f"id: {s.getId()}, type: {s.getType()}, def: {s.getDef()}")

    def set_robot_axis_angle(self, axis, angle, name="amy"):
        if name in self.rotation_fields:
            self.rotation_fields[name].setSFRotation(list(np.append(axis, angle)))

    def set_robot_rpy(self, rpy, name="amy"):
        axis, angle = transforms3d.euler.euler2axangle(rpy[0], rpy[1], rpy[2], axes='sxyz')
        self.set_robot_axis_angle(axis, angle, name)

    def set_robot_quat(self, quat, name="amy"):
        axis, angle = transforms3d.quaternions.quat2axangle([quat[3], quat[0], quat[1], quat[2]])
        self.set_robot_axis_angle(axis, angle, name)

    def set_robot_position(self, pos, name="amy"):
        if name in self.translation_fields:
            self.translation_fields[name].setSFVec3f(list(pos))

    def set_robot_pose_rpy(self, pos, rpy, name="amy"):
        self.set_robot_position(pos, name)
        self.set_robot_rpy(rpy, name)

    def set_robot_pose_quat(self, pos, quat, name="amy"):
        self.set_robot_position(pos, name)
        self.set_robot_quat(quat, name)

    def get_robot_position(self, name="amy"):
        if name in self.translation_fields:
            return self.translation_fields[name].getSFVec3f()

    def get_robot_orientation_axangles(self, name="amy"):
        if name in self.rotation_fields:
            return self.rotation_fields[name].getSFRotation()

    def get_robot_orientation_rpy(self, name="amy"):
        ax_angle = self.get_robot_orientation_axangles(name)
        return list(transforms3d.euler.axangle2euler(ax_angle[:3], ax_angle[3], axes='sxyz'))

    def get_robot_orientation_quat(self, name="amy"):
        ax_angle = self.get_robot_orientation_axangles(name)
        # transforms 3d uses scalar (i.e. the w part in the quaternion) first notation of quaternions, ros uses scalar last
        quat_scalar_first = transforms3d.quaternions.axangle2quat(ax_angle[:3], ax_angle[3])
        quat_scalar_last = np.append(quat_scalar_first[1:], quat_scalar_first[0])
        return list(quat_scalar_last)

    def get_robot_pose_rpy(self, name="amy"):
        return self.get_robot_position(name), self.get_robot_orientation_rpy(name)

    def get_robot_pose_quat(self, name="amy"):
        return self.get_robot_position(name), self.get_robot_orientation_quat(name)
