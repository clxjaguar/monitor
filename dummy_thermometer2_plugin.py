#!/usr/bin/env python3
# -*- coding: utf-8 -*-

class MonitorPlugin():
	def __init__(self, handlers):
		print("Dummy thermometer plugin init")
		self.parametersSet = handlers['parametersSet']
		self.value = 37
		self.initialValue = 39.2

	def load(self):
		self.parameter = self.parametersSet.addParameter("simulated-temp2", u'TEMP2', u'°C',  u'Temperature', '#FFFF00', "%.1f", 36,  38)
		self.parameter.info = "SIMULATED"
		self.parameter.updateValue(self.initialValue)

	def unload(self):
		self.parametersSet.removeParameter(self.parameter.ident)

	def __del__(self):
		print("Dummy thermometer deleted")
