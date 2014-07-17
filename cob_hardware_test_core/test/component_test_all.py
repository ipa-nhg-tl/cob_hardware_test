#!/usr/bin/env python
import sys
import time
import math

# ROS imports
import roslib
roslib.load_manifest('cob_hardware_test_core')
import rospy

# msg imports
from trajectory_msgs.msg import *
from sensor_msgs.msg import *
from pr2_controllers_msgs.msg import *
from diagnostic_msgs.msg import *
from cob_relayboard.msg import *

# care-o-bot includes
from simple_script_server import *
from dialog_client import *


class ComponentTestAll:
	def __init__(self):
		rospy.init_node('component_test_all')
		
		### PARAMETERS ###
		self.max_init_tries = 1		# maximum initialization tries for each component
		self.wait_time = 1			# waiting time (in seconds) before trying initialization again
		self.wait_time_diag = 1		# waiting time in seconds 
		self.test_numbers = 2		# number of test repeats
		
		# Make logfile
		complete_name = '/home/nhg-tl/Documents/AllComponentsTest/results/component_test_results_%s.txt' %(time.strftime("%Y%m%d"))
		self.log_file = open(complete_name,'w')
		
		# Message types
		self.actuator_msg = JointTrajectoryControllerState
		self.scan_msg = LaserScan
		self.kinect_msg = PointCloud2
		self.image_msg = Image
		
		self.msg_received = False
		self.sss = simple_script_server()		
		
		### GET PARAMETERS ###
		self.base_goals = None
		self.actuators = []
		self.sensors = []
		# Get base goals
		try:
			params_base = rospy.get_param('~component_test/base/goals')
			self.base_goals = params_base
		except:
			raise NameError('###############')
		# Get actuator parameters
		try:
			params_actuator = rospy.get_param('~component_test/actuators')
			i=0
			for k in params_actuator.keys():
				self.actuators.append(params_actuator[k])
				i+=1
		except:
			raise NameError('###############')
		# Get sensor parameters
		try:
			params_sensors = rospy.get_param('~component_test/sensors')
			i=0
			for k in params_sensors.keys():
				self.sensors.append(params_sensors[k])
				i+=1
		except:
			raise NameError('###############')
			
		# Subscribe to em-stop topic
		self.em_msg_received = False
		sub_em_stop = rospy.Subscriber("/emergency_stop_state", EmergencyStopState, self.cb_em_stop)
		em_stop_abort_time = rospy.Time.now() + rospy.Duration(self.wait_time)
		while not self.em_msg_received and rospy.get_rostime() < em_stop_abort_time:
			rospy.sleep(0.1)
		if not self.em_msg_received:
			self.em_stop_pressed = 'NO MSG'
		
		## TODO: Check that all the parameters (targets, topic, etc..) are set properly for each component
		## TODO: Check that at least one of the components (base, actuator, sensor) is received from param server
		## TODO: Improve cb_function selection in check_msg function
		
		# Save test info to results file
		self.log_file.write('Component test %s' %(time.strftime('%d.%m.%Y')))
		self.log_file.write('\n\nTested components: \n')
		if self.base_goals != None:
			self.log_file.write('- base\n')
		try:
			for actuator in self.actuators:
				self.log_file.write('- ' + actuator['name'] + '\n')
		except: pass
		try:
			for sensor in self.sensors:
				self.log_file.write('- ' + sensor['name'] + '\n')
		except: pass
		self.log_file.write('\n\n')
	
	
	### RUN ###
	def run(self):
		self.test_count = 0
		self.diag_count = None
		while self.test_count < self.test_numbers:
			# Init actuators
			for component in self.actuators:
				self.init_component(component['name'], component['topic'], component['msg_type'])
			# Move base
			self.move_base(self.base_goals)
			# Move actuators
			for component in self.actuators:
				self.move_component(component, component['test_target'])
				self.move_component(component, component['default_target'])
			# Test sensors
			for component in self.sensors:
				self.test_sensor(component)
			
					
			self.test_count += 1
		self.log_file.close()
	
	
	def init_component(self, component, topic, msg_type):
		init_tries_count = 0
		init_complete = False
		
		while not init_complete:
			init_handle = self.sss.init(component)
			init_tries_count += 1
			
			if self.check_msg(topic, msg_type):
				init_complete = True
			elif init_tries_count >= self.max_init_tries:
				init_complete = True
				dialog_client(0, 'Could not initialize component ' + component)
				#raise NameError('Could not initialize component ' + component)
	
	
	
	def check_msg(self, topic, msg_type):
		self.msg_received = False
		if str(msg_type) == "JointTrajectoryControllerState": cb_func = self.cb_actuator
		elif msg_type == "LaserScan": cb_func = self.cb_scanner
		elif msg_type == "PointCloud2": cb_func = self.cb_point_cloud
		elif msg_type == "Image": cb_func = self.cb_camera
		else: raise NameError('Unknown message! No callback function defined for message type <<%s>>' %(msg_type))
		
		sub_state_topic = rospy.Subscriber(str(topic), eval(msg_type), cb_func)
		abort_time = rospy.Time.now() + rospy.Duration(self.wait_time)
		
		while not self.msg_received and rospy.get_rostime() < abort_time:
			rospy.sleep(0.1)
		sub_state_topic.unregister()
		
		if self.msg_received:
			return True
		return False
	
	
			
	### Sensor test ###
	def test_sensor(self, component):
		if not self.check_msg(component['topic'], component['msg_type']):
			message = 'No message received from sensor <<%s>> \TOPIC: %s' %(component['name'], component['topic'])
			self.log_diagnostics(component, message)
		
	
	def move_base(self, base_goals):
		i = 0
		while True:
			next_goal = 'test_%s'%(i)
			if next_goal in base_goals:
				dialog_client(0, str(base_goals[next_goal]))
				move_handle = self.sss.move("base", base_goals[next_goal])
				if move_handle.get_state() != 3:
					raise NameError('Could not move base to %s. errorCode: %s' %(next_goal, move_handle.get_error_code()))
				move_handle.wait()
				i += 1
			else: break
			
		# Back to default position
		move_handle = self.sss.move("base",base_goals['test_0'])
		if move_handle.get_state() != 3:
			raise NameError('Could not move base to test_0. errorCode: %s' %(move_handle.get_error_code()))
		move_handle.wait()
		
	
	def move_component(self, component, target):
		
		# Subscribe to component's state topic to get its current position
		#sub_position = rospy.Subscriber(topic, msg_type, self.cb_actuator)
		
		# Move to test position
		move_handle = self.sss.move(component['name'], target)
		if move_handle.get_state() != 3:
			raise NameError('Could not move component %s to target position. errorCode: %s' %(component['name'], move_handle.get_error_code()))
		move_handle.wait()
		
		# Check if the target position is really reached
		if self.check_msg(component['topic'], component['msg_type']):
			actual_pos = self.actuator_position
		else: raise NameError('Couldn''t get the actual position of component <<%s>>' %(component))
		
		target_pos = rospy.get_param("/script_server/" + component['name'] + "/" + target)
		target_pos = target_pos[len(target_pos) - 1]
		for i in range(len(target_pos)):
			if math.fabs(target_pos[i] - actual_pos[i]) > component['error_range']:
				raise NameError('Target position out of error range! \n\nTarget_position: %s \nActual_position: %s \nError_range: %s' %(target_pos, actual_pos, component['error_range']))

		

	def log_diagnostics(self, component, message):
		if self.diag_count != self.test_count:
			self.log_file.write('ROUND %s\n\n' %(self.test_count))
			
		self.log_file.write("FAIL: " + message + '\n')
		
		if self.em_stop_pressed:
			self.log_file.write('EMERGENCY STOP ACTIVE\n')
		
		### GET DIAGNOSTICS ###
		# Wait for the message
		self.msg_received = False
		sub_diagnostics = rospy.Subscriber("/diagnostics", DiagnosticArray, self.cb_diagnostics)
		abort_time = rospy.Time.now() + rospy.Duration(self.wait_time)
		while not self.msg_received and rospy.get_rostime() < abort_time:
			rospy.sleep(0.1)
		
		# Get diagnostics from /diagnostics topic
		name = '%s_controller' %(component['name'])
		diag_name = ""
		abort_time = rospy.Time.now() + rospy.Duration(self.wait_time_diag)
		while diag_name != name and rospy.get_rostime() < abort_time:
			diagnostics = str(self.diagnostics_status)
			diag_name = diagnostics.replace("/","")
			diag_name = (diag_name.split("name: ", 1)[1]).split("\n",1)[0]
		sub_diagnostics.unregister()
		
		self.log_file.write('DIAGNOSTICS: ')
		if diag_name == name:
			self.log_file.write('\n' + diagnostics + "\n\n")
		else:
			self.log_file.write("No diagnostics found by name \"" + name + "\"\n\n")
		self.diag_count = self.test_count
	
	
			
	### CALLBACKS ###
	def cb_em_stop(self, msg):
		self.em_stop_pressed = msg.emergency_button_stop
		self.em_msg_received = True
		
	def cb_actuator(self, msg):
		self.actuator_position = msg.actual.positions
		self.msg_received = True

	def cb_scanner(self, msg):
		self.scanner_msg = msg.ranges
		self.msg_received = True

	def cb_point_cloud(self, msg):
		self.point_cloud_msg = msg.fields
		self.msg_received = True

	def cb_camera(self, msg):
		self.camera_msg = msg.data
		self.msg_received = True
		
	def cb_diagnostics(self, msg):
		self.diagnostics_status = msg.status
		self.msg_received = True

if __name__ == "__main__":
	try:
		TEST = ComponentTestAll()
		TEST.run()
	except KeyboardInterrupt, e:
		pass
	print "exiting"