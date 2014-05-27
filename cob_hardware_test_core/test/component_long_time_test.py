#!/usr/bin/env python
import roslib
roslib.load_manifest('cob_hardware_test_core')
import sys
import time
import unittest
import math
import numpy

import rospy
import rostest
from trajectory_msgs.msg import *
from simple_script_server import *
from pr2_controllers_msgs.msg import *
from dialog_client import *



class UnitTest(unittest.TestCase):
	def __init__(self, *args):
		super(UnitTest, self).__init__(*args)
		rospy.init_node('component_long_time_test')
		self.message_received = False
		self.sss = simple_script_server()
		self.command_traj = JointTrajectory()
		# get parameters
		try:
			# component
			if not rospy.has_param('~component'):
				self.fail('Parameter component does not exist on ROS Parameter Server')
			self.component = rospy.get_param('~component')
			# movement command
			if not rospy.has_param('~test_target'):
				self.fail('Parameter test_target does not exist on ROS Parameter Server')
			self.test_target = rospy.get_param('~test_target')
			# movement command
			if not rospy.has_param('~default_target'):
				 self.fail('Parameter default_target does not exist on ROS Parameter Server')
			self.default_target = rospy.get_param('~default_target')
			# time to wait before
			self.wait_time = rospy.get_param('~wait_time', 5)
			# error range
			if not rospy.has_param('~error_range'):
				self.fail('Parameter error_range does not exist on ROS Parameter Server')
			self.error_range = rospy.get_param('~error_range')
		except KeyError, e:
			self.fail('Parameters not set properly')
		print """
			  Component: %s  
			  Targets: %s , %s
			  Wait Time: %s
			  Error Range: %s""" % (self.component, self.default_target, self.test_target, self.wait_time, self.error_range)
		# check parameters
		# \todo do more parameter tests
		if self.error_range < 0.0:
			error_msg = "Parameter error_range should be positive, but is " + self.error_range
			self.fail(error_msg)
		if self.wait_time < 0.0:
			error_msg = "Parameter wait_time should be positive, but is " + self.wait_time
			self.fail(error_msg)

		# init subscribers
		state_topic = "/" + self.component + "_controller/state"
		sub_state_topic = rospy.Subscriber(state_topic, JointTrajectoryControllerState, self.cb_state)

	def test_component(self):
		
		# init component
		init_handle = self.sss.init(self.component)
		if init_handle.get_error_code() != 0:
		  error_msg = 'Could not initialize ' + self.component
		  self.fail(error_msg)

		# start actual test
		print "Waiting for messages"
		#give the topics some seconds to receive messages
		abort_time = rospy.Time.now() + rospy.Duration(self.wait_time)
		while not self.message_received and rospy.get_rostime() < abort_time:
		 #   print "###debug here###"
			rospy.sleep(0.1)
						
		if not self.message_received:
			self.fail('No state message received within wait_time(%s) from /%s_controller/state' % (self.wait_time, self.component))

		self.assertTrue(dialog_client(0, 'Ready to start the %s test?' % (self.component)))

		# execute movement to test_target and back to default_target
		self.execute_movement()

	def execute_movement(self):
		tilt_amount = 1.0 # the amount of tilt during the torso rotation
		
		# start rotating the torso
		while not rospy.is_shutdown():
			for i in numpy.arange(0, 6.26, 1.25):
				joint_3 = float(i - tilt_amount)
				joint_1 = float(-i)
				circle_target_point = [[joint_1, tilt_amount, joint_3]]
				move_handle = self.sss.move(self.component, circle_target_point)
				self.assertEqual(move_handle.get_state(), 3)
				if move_handle.get_error_code() != 0:
					error_msg = 'Could not move ' + self.component
					self.fail(error_msg + "; errorCode: " + str(move_handle.get_error_code()))
				self.check_target_reached(circle_target_point)
			# move back to home position
			move_handle = self.sss.move(self.component, [[joint_1, 0.0, joint_3 + tilt_amount]])
			move_handle = self.sss.move(self.component, [[joint_1/2, 0.0, (joint_3 + tilt_amount)/2]])
			move_handle = self.sss.move(self.component, [[0.0, 0.0, 0.0]])
			self.assertTrue(dialog_client(1, 'Continue the test?'))
			
	def check_target_reached(self,target):
		# get commanded trajectory
		command_traj = target
		print command_traj

		# get last point out of trajectory
		traj_endpoint = command_traj[len(command_traj) - 1]
		print traj_endpoint

		actual_pos = self.actual_pos # fix current position configuration for later evaluation

		# checking if target position is really reached
		print "actual_pos = ", actual_pos
		print "traj_endpoint = ", traj_endpoint
		for i in range(len(traj_endpoint)):
			self.assert_(((math.fabs(traj_endpoint[i] - actual_pos[i])) < self.error_range), "Target position out of error_range")

		#self.assertTrue(dialog_client(1, 'Did <<%s>> reach <<%s>>?' % (self.component, target)))

	# callback functions
	def cb_state(self, msg):
		self.actual_pos = msg.actual.positions
		self.message_received = True


if __name__ == '__main__':
	# Copied from hztest: A dirty hack to work around an apparent race condition at startup
	# that causes some hztests to fail. Most evident in the tests of
	# rosstage.
	time.sleep(0.75)
	try:
		rostest.run('rostest', 'component_long_time_test', UnitTest, sys.argv)
	except KeyboardInterrupt, e:
		pass
	print "exiting"
