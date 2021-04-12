#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import usb_oximeter, threading

class MonitorPlugin():
	def __init__(self, parametersSet, tracesSet):
		print("USB Oximeter plugin init")
		self.parametersSet = parametersSet
		self.tracesSet = tracesSet
		self.beat = 0

	def load(self):
		self.parameterPR  = self.parametersSet.addParameter("pr",   u'PR',   u'bpm', u'Pulse Rate',  '#00d000', "%.0f", 50, 120)
		self.parameterSAT = self.parametersSet.addParameter("sat",  u'SpO₂', u'%',   u'Saturation', '#50ccff', "%.0f", 93, 100)
		self.tracePleth = self.tracesSet.addTrace("pleth", color='#50ccff')

		self.oxi1 = usb_oximeter.Oximeter()
		self.oxi1.assignSerialPorts(("/dev/ttyUSB0", "/dev/ttyUSB1"))
		self.oxi1.setCallback(self._oximeterCallback)

		thread = threading.Thread(target=self.oxi1.worker)
		thread.daemon = True
		thread.start()

	def unload(self):
		self.oxi1.stop()
		self.parametersSet.removeParameter(self.parameterPR.ident)
		self.parametersSet.removeParameter(self.parameterSAT.ident)
		self.tracesSet.removeTrace(self.tracePleth.ident)

	def __del__(self):
		print("USB Oximeter deleted")

	def _oximeterCallback(self, SpO2, pulse_rate):
		if (SpO2 != 0):
			self.parameterSAT.updateValue(SpO2)
		else:
			self.parameterSAT.updateValue(float('nan'))

		if (pulse_rate != 0):
			self.parameterPR.updateValue(pulse_rate)
		else:
			self.parameterPR.updateValue(float('nan'))

		if (self.oxi1.SpO2dropping):
			self.parameterPR.info = ""
			self.parameterSAT.info = "SPO2 DROPPING!"
		elif (self.oxi1.probeError):
			self.parameterPR.info = "PROBE ERROR"
			self.parameterSAT.info  = "PROBE ERROR"
		elif (self.oxi1.searchingTooLong):
			self.parameterPR.info = "SEARCHING!"
			self.parameterSAT.info = "SEARCHING!"
		elif (self.oxi1.searching):
			self.parameterPR.info = "SEARCHING"
			self.parameterSAT.info = "SEARCHING"
		else:
			self.parameterSAT.info = str('S'+str(self.oxi1.signalStrength)+' '+self.oxi1.bargraphValue*'|')

		if (self.oxi1.pulse):
			self.beat = 5
			self.parameterPR.info = u'❤'
			self.parameterPR.nextRefresh = 0
		elif self.beat:
			self.beat-=1
			if self.beat == 0:
				self.parameterPR.info = ""

		# update data for fast curve ...
		self.tracePleth.addPoint(self.oxi1.waveformValue)
