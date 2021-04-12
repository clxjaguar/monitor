#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import random, time, threading

class MonitorPlugin():
	def __init__(self, parametersSet, tracesSet):
		print("Dummy thermometer plugin init")
		self.parametersSet = parametersSet
		self.tracesSet = tracesSet
		self.value = 37
		self.initialValue = 37

	def load(self):
		self.parameter = self.parametersSet.addParameter("simulated-temp", u'TEMP', u'°C',  u'Temperature', '#FF5000', "%.1f", 36,  38)
		# ~ self.traceUseless = self.tracesSet.addTrace("therm", color='#ff5000')
		self.parameter.info = "SIMULATED"
		self.parameter.updateValue(self.initialValue)
		thread = threading.Thread(target=self._worker)
		thread.daemon = True
		thread.start()
		# ~ self.parametersSet.removeParameter(self.parameter.ident)

	def unload(self):
		self.parametersSet.removeParameter(self.parameter.ident)

	def __del__(self):
		print("Dummy thermometer deleted")

	def _worker(self):
		while(True):
			self.value += (random.random()-.5)*.1
			self.value = self.value*.95 + self.initialValue*.05
			self.parameter.updateValue(self.value)
			time.sleep(1)

