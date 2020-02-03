#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Module for the somewhat generic brand pulse oximeter. It's VCP based
# mine is 10c4:ea60, CP2102 USB to UART. I really need to find a name for this.
# "USB Oximeter PC based Pulse Oximeter SpO2 monitor usb probe (1 cable + 1 adult sensor)"
#
# Beginning of the reverse engineering in 2018-09-17 by @cLxJaguar
#
# sudo apt-get install python-pip python-setuptools
# pip install --upgrade pip
# sudo pip install -U pyserial

import serial, sys, time, math

class Oximeter:
	def __init__(self, serialPort=None):
		self.device = None; self.opened = False; self.serialport = None; self.exitLoop = False
		self.serialPorts = (serialPort)
		self.callback = None
		self._resetParameters()

		if serialPort:
			self.open(serialPort)

	def assignSerialPorts(self, serialPorts):
		if serialPorts.__class__.__name__ in ('list', 'tuple'):
			self.serialPorts = serialPorts
		else:
			self.serialPorts = [serialPorts]

	def open(self, serialPort):
		self.device = serial.Serial(serialPort, 19200, xonxoff=False, rtscts=False, dsrdtr=False, timeout=1, parity=serial.PARITY_ODD)
		self.serialPort = serialPort
		self.opened = True

	def close(self):
		if self.opened:
			self.device.close()
			self.opened = False
			self.probeError = True

	def stop(self):
		self.exitLoop = True
		self.probeError = True

	def setCallback(self, callback):
		self.callback = callback

	def _resetParameters(self):
		self.SpO2 = 0
		self.pulseRate = 0
		self.signalStrength = 0
		self.waveformValue = 64
		self.bargraphValue = 0
		self.pulse = False
		self.pulseLast = False
		self.SpO2dropping = False
		self.searching = False
		self.searchingTooLong = False
		self.probeError = True
		self.beat_time=0
		self.unfiltered_pulse_rate=0

	def worker(self):
		print "Thread started: OximeterWorker()"
		count=-1
		i = 0
		t = 0
		values=10*[0]
		while(not self.exitLoop):
			try:
				if self.opened:
					b = ord(self.device.read(1))
					if (count>=0):
						count+=1
					if (bool(b&128)): # frame sync
						count = 0
					values[count] = b
					if (count!=4):
						continue
				else:
					if t>=math.pi*2:
						t=0.05
						# try to open the port!
						if self.serialPorts is None:
							continue
						port = self.serialPorts[i]
						i+=1
						if i >= len(self.serialPorts):
							i = 0
						sys.stderr.write("Oximeter thread: trying to open: "+port+"\n")
						self.open(port)
						count=-1
						continue
					else:
						self.waveformValue = 64+32*math.sin(t)
						self.signalStrength = 0
						self.callback(0, 0)
						time.sleep(0.01)
						t+=0.05
						continue

			except KeyboardInterrupt:
				self.stop()

			except serial.SerialException:
				sys.stderr.write("Oximeter SerialException: "+str(sys.exc_info()[1])+"\n")
				self._resetParameters()
				self.close()
				self.probeError = True; count=-1;
				self.callback(0, 0)
				continue

			except:
				sys.stderr.write("Oximeter Error: "+str(sys.exc_info()[1])+"\n")
				self._resetParameters()
				self.close()
				self.probeError = True; count=-1;
				self.callback(0, 0)
				continue

			self.SpO2 = values[4]
			self.pulseRate = values[3]
			self.signalStrength = values[0]&15
			self.waveformValue = values[1]&127
			self.bargraphValue = values[2]&15
			if values[0]&64:
				if not self.pulseLast:
					self.pulse = True
				else:
					self.pulse = False
				self.pulseLast = self.pulse
			else:
				self.pulse = False
				self.pulseLast = False
			self.SpO2dropping = bool(values[0]&32)
			self.searching = bool(values[2]&32)
			self.searchingTooLong = bool(values[0]&16)
			self.probeError = bool(values[2]&16)

			self.callback(self.SpO2, self.pulseRate)
		self.close()
		print "Thread stopped: OximeterWorker()"


def OximeterDemo(SpO2, pulse_rate):
	global dev
	sys.stdout.write("SpO²:%3d\tBPM:%4d" % (SpO2, pulse_rate))

	if dev.pulse:
		sys.stdout.write(" [beat]")

	if dev.SpO2dropping:
		sys.stdout.write(" [SpO² dropping]")

	if dev.probeError:
		sys.stdout.write(" [probe error]")

	if dev.searching:
		sys.stdout.write(" [searching signal]")

	if dev.searchingTooLong:
		sys.stdout.write(" [searching for too long]")

	sys.stdout.write("\n")
	sys.stdout.flush()

if __name__ == '__main__':
	global dev
	dev = Oximeter()
	dev.assignSerialPorts("/dev/ttyUSB0")
	dev.setCallback(OximeterDemo)
	dev.worker()
	dev.stop()
