#!/usr/bin/python3

import numpy as np
from numpy import linalg as LA
import random
import matplotlib.pyplot as plt
from matplotlib import style
import pandas as pd
import seaborn as sns
import math
import cntk as C

class feature_extractor:
	
	def __init__(self, feature_vector, target_vector, learning_rate, name='feature_predicter'):
		self._input_size = feature_vector
		self._output_size = (1,feature_vector[1])
		self._target_size = target_vector
		self._input = C.sequence.input_variable(self._input_size)
		self._target = C.sequence.input_variable(self._target_size)
		self._output = C.sequence.input_variable(self._output_size)
		print(self._output)
		self.name = name
		self._batch_size = 24
		self._max_iter = 1000000
		self._lr_schedule = C.learning_rate_schedule([learning_rate * (0.997**i) for i in range(1000)], C.UnitType.sample, epoch_size=round(self._max_iter*self._batch_size/100))
		self._model,self._loss, self._learner, self._trainer = self.create_model()

	def create_model(self):
		model1i = C.layers.Sequential([
			# Convolution layers
			C.layers.Convolution2D((1,3), num_filters=8, pad=True, reduction_rank=0, activation=C.ops.tanh,name='conv_f'),
			C.layers.Convolution2D((1,3), num_filters=16, pad=True, reduction_rank=1, activation=C.ops.tanh,name='conv2_f'),
			C.layers.Convolution2D((1,3), num_filters=32, strides=(1,3), pad=False, reduction_rank=1, activation=C.ops.tanh,name='conv3_f'),
			######
			# Dense layers
			C.layers.Dense(32, activation=C.ops.relu,name='dense1_f'),
			#C.layers.Dense(32, activation=C.ops.relu,name='dense1_f'),
			#C.layers.Dense(16, activation=C.ops.relu,name='dense1_f')
		]) (self._input)

		### target
		model1t = C.layers.Sequential([
			#C.layers.Dense(16, activation=C.ops.relu,name='dense2_f'),
			C.layers.Dense(32, activation=C.ops.relu,name='dense3_f')
		]) (self._target)

		### concatenate both processed target and observations
		inputs = C.ops.splice(model1i,model1t)

		### Use input to predict next hidden state, and generate
		### next observation
		model1 = C.layers.Sequential([
			C.layers.Dense(64, activation=C.ops.relu),
			######
			# Recurrence
			C.layers.Recurrence(C.layers.LSTM(2048, init=C.glorot_uniform()),name='lstm_f'),
			######
			# Prediction
			#C.layers.Dense(16, activation=C.ops.relu,name='predict'),
			######
			# Decoder layers
			C.layers.Dense(256, activation=C.ops.relu,name='dense4_f'),
			#C.layers.Dense(64, activation=C.ops.relu,name='dense2'),
			C.layers.Dense(114, activation=C.ops.relu,name='dense5_f')
		])(inputs)

		######
		# Reshape output
		model2 = C.ops.reshape(model1,(1,1,114))

		model3 = C.layers.Sequential([
			######
			# Deconvolution layers
			C.layers.ConvolutionTranspose((1,7), num_filters=8, strides=(1,1), pad=False, bias=False, init=C.glorot_uniform(1),name='deconv1'),
			C.layers.ConvolutionTranspose((1,3), num_filters=4, strides=(1,3), pad=False, bias=False, init=C.glorot_uniform(1),name='deconv2'),
			C.layers.ConvolutionTranspose((1,3), num_filters=1,  pad=True,name='deconv3')
		])(model2)

		model = C.ops.reshape(model3,(1,360))

		err = C.ops.reshape(C.ops.minus(model,self._output), (self._output_size))
		sq_err = C.ops.square(err)
		mse = C.ops.reduce_mean(sq_err)
		rmse_loss = C.ops.sqrt(mse)
		rmse_eval = rmse_loss

		learner = C.adadelta(model.parameters)
		progress_printer = C.logging.ProgressPrinter(tag='Training')
		trainer = C.Trainer(model, (rmse_loss,rmse_eval), learner, progress_printer)
		return model, rmse_loss, learner, trainer

	def train_network(self, data, targets):
		for i in range(self._max_iter):
			input_sequence,target_sequence,output_sequence = self.sequence_minibatch(data, targets, self._batch_size)
			self._trainer.train_minibatch({self._input: input_sequence, self._target: target_sequence, self._output: output_sequence})
			self._trainer.summarize_training_progress()
			if i%10 == 0:
				self._model.save('feature_predicter.dnn')

	def sequence_minibatch(self, data, targets, batch_size):
		sequence_keys    = list(data.keys())
		minibatch_keys   = random.sample(sequence_keys,batch_size)
		minibatch_input  = []
		minibatch_target = []
		minibatch_output = []

		for key in minibatch_keys:
			_input,_target,_ouput = self.input_output_sequence(data,targets,key)
			minibatch_input.append(_input)
			minibatch_target.append(_target)
			minibatch_output.append(_ouput)
		
		return minibatch_input,minibatch_target,minibatch_output
	
	def input_output_sequence(self, data, targets, seq_key):
		data_k = data[seq_key]
		input_sequence = np.zeros((len(data_k)-2,self._input_size[0],self._input_size[1]), dtype=np.float32)
		target_sequence = np.zeros((len(data_k)-2,self._target_size[0],self._target_size[1]), dtype=np.float32)
		output_sequence = np.zeros((len(data_k)-2,self._output_size[0],self._output_size[1]), dtype=np.float32)

		for i in range(0,len(data_k)-2):
			input_sequence[i,0,:]  = data_k[i]
			input_sequence[i,1,:]  = data_k[i+1]
			target_sequence[i,:,:] = targets[seq_key][i]
			output_sequence[i,0,:] = data_k[i+2]
		return input_sequence,target_sequence,output_sequence

