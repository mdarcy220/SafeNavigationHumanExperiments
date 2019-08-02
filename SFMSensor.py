#!/usr/bin/python3

from Robot import Robot#RobotControlInput

import cntk as C
import numpy as np
import Vector
import sys
import math
## A navigation algorithm based on an RNN that predicts the next action.
#
class SFMSensor():

	def __init__(self,Robot,target,cmdargs):
		self._target  = target;
		self._cmdargs = cmdargs;
		self._alg = 'ours' #'target' # 'ours'
		# Parameters from paper
		self._kappa = 2.3
		#self._kappa = 0.5
		self._A = 2.66
		self._B = 0.79
		self._d = 0.4
		self._l = 0.59
		self._alpha = 0.6
		self._gamma = 0.02
		self._delta = 0.02
		self._robot = Robot;
		self.debug_info = {'min_proximities': []};
		self._min_cur_radar_scans = sys.maxsize
		self._gps = self._robot._sensors['gps']
		self._radar  = self._robot._sensors['radar']
		self._start_pos = np.copy(self._gps.location());
		self._last_radar_data = self._radar.scan(self._gps.location())
		self.count = 0
		self.SfM = np.array([[0,0]]).T
		self.human_vect = np.array([[0,0]]).T
		self.obs_vect = np.array([[0,0]]).T
		self.target_vect = np.array([[0,0]]).T
		self._old_position = None


	## Select the next  the robot
	#
	# This function uses the robot's radar and location information, as
	# well as internally stored information about previous locations,
	# to compute the next action the robot should take.

	# @returns (`Robot.RobotControlInput` object)
	# <br>	-- A control input representing the next action the robot
	# 	should take.
	#
	def select_next_action(self):
		self._min_cur_radar_scans = sys.maxsize
		humans = self._create_human_data()
		obstacles = self._create_obstacles_data()
		self.debug_info['min_proximities'].append(self._min_cur_radar_scans)
		location = self._gps.location()
		## we might need to limit te magnitude of this vector
		v_0 = self._get_target_direction_input_data()
		if self.count == 0:
			v = 0.05*Vector.unit_vec_from_radians(Vector.radians_between(location, self._target.position))
			theta = math.atan2(v[1],v[0])
			self._old_position = self._start_pos
		else:
			v = location - self._old_position
			theta = math.atan2(v[1],v[0])
			self._old_position = location
		#v_0 = v_0*0.306/math.sqrt(np.sum(np.power(v_0,2)))
		v_0 = v_0*np.linalg.norm(v)/math.sqrt(np.sum(np.power(v_0,2)))
		force = self.force(v_0,v,np.array([location[0],location[1],theta]) ,humans,obstacles)
		#force = force*0.306/math.sqrt(np.sum(np.power(force,2)))
		force_norm = math.sqrt(np.sum(np.power(force,2)))
		force = force*0.306/force_norm if force_norm>0.306 else force
		self.SfM = np.reshape(force,(2,1));
		#v_next = v + force*1
		#speed = math.sqrt(np.sum(np.power(v_next,2)))
		#direction = math.atan2(v_next[1],v_next[0])*180/math.pi
		self.count += 1

		
		#return RobotControlInput(speed, direction);

	def _get_target_direction_input_data(self):
		target_vec	= np.subtract(self._target.position, self._gps.location())
		return target_vec

	def _create_obstacles_data(self):
		## humans
		radar_data, data_obj, intersections = self._radar.scan_static_obstacles_one_by_one(self._gps.location())
		self._min_cur_radar_scans = min(np.min(radar_data), self._min_cur_radar_scans)
		objects = list(set(data_obj))
		if None in objects:
			objects.remove(None)
		data = []
		data_vect = [i for i,x in enumerate(data_obj) if x != None]
		for obj in objects:
			data_object = {}
			the_min  = -1
			min_value = float('inf')
			for i in data_vect:
				if data_obj[i]._obs_id != obj._obs_id:
					continue
				if radar_data[i] <  min_value:
					min_value = radar_data[i]
					the_min = i

			#the_min = np.argmin([radar_data[i] for i in data_vect if data_obj[i]._obs_id == obj._obs_id])
			data_object['distance'] = radar_data[the_min] 
			data_object['position'] = intersections[:,the_min]
			data.append(data_object)
		return data

	def _create_human_data(self):
		## humans
		radar_data, data_obj, _ = self._radar.scan_dynamic_obstacles_one_by_one(self._gps.location())
		self._min_cur_radar_scans = min(np.min(radar_data), self._min_cur_radar_scans)
		objects = list(set(data_obj))
		if None in objects:
			objects.remove(None)
		data = []
		data_vect = [i for i,x in enumerate(data_obj) if x != None]
		for obj in objects:
			data_object = {}

			data_object['distance'] = min([radar_data[i] for i in data_vect if data_obj[i]._obs_id == obj._obs_id])
			data_object['position'] = obj.coordinate
			data.append(data_object)

		return data

	def force(self,v_0, v, pose, humans, objs):
		"""
		Parameters:
		v_0 -- a numpy array of the shape (2x1) or (2,)
		v   -- a numpy array of the shape (2x1) or (2,)
		pose -- tuple or list of the shape (x,y,theta) or [x,y,theta]
		humans -- list of objects (currently should be ellipses)
		obstacles -- list of arbitraty objects
		object -- object instantiation.
		"""
		force = np.zeros((2,))
		# force to target:
		if self._alg == 'ours':
			force_to_target = self._alpha*self._kappa *v_0/np.linalg.norm(v_0)
			force_to_target *=  1 - np.dot(v_0,v)/(np.linalg.norm(v_0)*np.linalg.norm(v))
			#force_to_target = (v_0-v)
			#force_norm = math.sqrt(np.sum(np.power(force_to_target,2)))
			#force_to_target = math.exp(force_norm)*v_0/math.sqrt(np.sum(np.power(v_0,2)))
			self.target_vect = np.reshape(force_to_target/self._alpha,(2,1));
		elif self._alg == 'target':
			v_0 = v*np.linalg.norm(v_0)/np.linalg.norm(v)
			force_to_target = self._alpha*self._kappa *(v_0-v)
			self.target_vect = np.reshape(force_to_target/self._alpha,(2,1));
			
		self.human_vect = np.array([[0,0]], dtype=np.float64).T
		self.obs_vect = np.array([[0,0]], dtype=np.float64).T
		for human in humans:
			pos = human['position']
			dis = human['distance']
			w = self.weight(pose,pos)
			f = self._A * math.exp(self._d - dis)/self._B
			direction = pos - pose[0:2]
			direction = direction /math.sqrt(np.sum(np.power(direction,2)))
			self.human_vect -= np.reshape(f*direction*w,(2,1))
			force -= self._gamma*f*direction*w
		for obj in objs:
			pos = obj['position']
			dis = obj['distance']
			w = self.weight(pose,pos)
			f = self._A * math.exp(self._d - dis)/self._B
			direction = pos - pose[0:2]
			direction = direction /math.sqrt(np.sum(np.power(direction,2)))
			self.obs_vect -= np.reshape(f*direction*w,(2,1))
			force -= self._delta*f*direction*w
		force += force_to_target

		return force
		
	def weight(self,pose_0, pose_1):
		"""
		returns the weight of the force based on its location
		"""
		phi = abs(math.atan2(pose_1[1] - pose_0[1],pose_1[0]-pose_0[0]) - pose_0[2])
		weight = self._l +(1-self._l)*(1+math.cos(phi))/2
		return weight
