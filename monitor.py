#!/usr/bin/env python
# -*- coding: utf-8 -*-

# sudo apt-get install python-pip python-pyside python-setuptools python-pyqtgraph
# pip install --user --upgrade pip
# pip install --user --upgrade pyserial

import os, sys, time, math, threading

def pipRun(command):
	print("$ "+command)
	os.system(command)

pipInstallRan = False
def pipInstall(package):
	if not '--pipInstallRan' in sys.argv:
		global pipInstallRan
		print("We want to install: "+package)
		if not pipInstallRan:
			pipInstallRan = True
			pipRun(sys.executable+" -m pip install --user --upgrade pip")
			pipRun(sys.executable+" -m pip install --user setuptools")
		pipRun(sys.executable+" -m pip install --user "+package)
	else:
		raise

try:
	from PyQt4.QtGui import *
	from PyQt4.QtCore import *
except:
	pipInstall("PyQt4")

try:
	import numpy
except:
	pipInstall("numpy")

try:
	import pyqtgraph # needs import PyQt4 before!
except:
	pipInstall("pyqtgraph")

try:
	import serial
except:
	pipInstall("pyserial")

if pipInstallRan:
	cmd = sys.executable+' '+' '.join(sys.argv)+' --pipInstallRan'
	print("Re-exec: "+cmd)
	time.sleep(1)
	os.system(cmd)
	exit(-1)

import usb_oximeter

class Parameter():
	def __init__(self, name, unit, color, format, vmin, vmax, plotid=0):
		self.name = name
		self.unit = unit
		self.color = color
		self.format = format
		self.value = float("nan")
		self.min = vmin
		self.max = vmax
		self.plotid = plotid
		self.info = ""
		self.trends = []

	def updateValue(self, value):
		self.value = value

	def copyValueToTrends(self):
		self.trends.append(self.value)

	def getValueStr(self):
		if (self.value != self.value):
			return('---')
		else:
			return(self.format % self.value)

PR = 0; SPO2 = 1; TEMP = 2
parameters = {}            # name     unit     color     format min  max  plotid
parameters[PR]   = Parameter(u'PR',   u'bpm', '#00d000', "%.0f", 50, 120, 0) # #87CEFA
parameters[SPO2] = Parameter(u'SpO₂', u'%',   '#50CCFF', "%.0f", 93, 100, 1)
parameters[TEMP] = Parameter(u'TEMP', u'°C',  '#FF5000', "%.1f", 36,  38, 2)
parameters[TEMP].updateValue(37.15); parameters[TEMP].info = "SIMULATED"

X_fast_oximeter = range(200); Y_fast_oximeter = 200*[0]; Y_fast_oximeter_index = 0; beat = False
def OximeterCallback(SpO2, pulse_rate):
	global oxi1, m1, beat, parameters
	global X_fast_oximeter, Y_fast_oximeter, Y_fast_oximeter_index

	if (SpO2 != 0):
		parameters[SPO2].updateValue(SpO2)
	else:
		parameters[SPO2].updateValue(float('nan'))
	if (pulse_rate != 0):
		parameters[PR].updateValue(pulse_rate)
	else:
		parameters[PR].updateValue(float('nan'))

	if (oxi1.SpO2dropping):
		parameters[PR].info = ""
		parameters[SPO2].info = "SPO2 DROPPING!"
		m1.div_refresh_values = 0
	elif (oxi1.probeError):
		parameters[PR].info = "PROBE ERROR"
		parameters[SPO2].info  = "PROBE ERROR"
		m1.div_refresh_values = 0
	elif (oxi1.searchingTooLong):
		parameters[PR].info = "SEARCHING!"
		parameters[SPO2].info = "SEARCHING!"
		m1.div_refresh_values = 0
	elif (oxi1.searching):
		parameters[PR].info = "SEARCHING"
		parameters[SPO2].info = "SEARCHING"
	else:
		parameters[PR].info = ""
		parameters[SPO2].info = str('S'+str(oxi1.signalStrength)+' '+oxi1.bargraphValue*'|')

	if (oxi1.pulse):
		beat = True
		m1.div_refresh_values = 0

	# update data for fast curve ...
	try:
		Y_fast_oximeter[Y_fast_oximeter_index] = oxi1.waveformValue
		Y_fast_oximeter_index+=1
		Y_fast_oximeter[Y_fast_oximeter_index] = float('nan')
	except:
		Y_fast_oximeter[0] = oxi1.waveformValue
		Y_fast_oximeter_index=1

class MonitorGUI(QWidget):
	def __init__(self):
		super(MonitorGUI, self).__init__()
		self.trends_time = []
		self.div_refresh_values = 0
		self.initUI()

	def initUI(self):
		self.setStyleSheet("\
			QWidget { background-color: #000000; color: #ffffff; } \
			QLabel { margin: 0px; padding: 0px; } \
			QSplitter::handle:vertical   { image: none; } \
			QSplitter::handle:horizontal { width:  2px; image: none; } \
			QPushButton { background-color: #404040; } \
			QLabel#c_names { font-size: 30pt; } \
			QLabel#c_units { font-size: 20pt; } \
			QLabel#c_limits { font-size: 10pt; } \
			QLabel#c_values { font-size: 70pt; padding-top: -16px; padding-bottom: -15px; } \
			QLabel#c_infos { font-size: 15pt; } \
			QLabel#clockLabel { color: #707070; font-size: 10pt; } \
			QLabel#clock { color: #ffffff; font-size: 15pt; } \
			QGroupBox { border: 1px solid #707070; border-radius: 8px; }\
		");

		# elements in the left part of the screen
		left_layout = QVBoxLayout()
		splitter1 = QSplitter(Qt.Vertical)

		splitter1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		left_layout.addWidget(splitter1)

		# pyqtgraph curves
		self.oximeter = pyqtgraph.PlotWidget()
		self.oximeter.showAxis('bottom', show=False)
		self.oximeter.showAxis('left', show=False)
		splitter1.addWidget(self.oximeter)

		plotids = []
		for i in parameters:
			plotids.append(parameters[i].plotid)

		self.trendsPw = []
		for i in plotids:
			axis = DummyAxis
			if i == len(plotids) - 1: axis = DateAxis
			pw = pyqtgraph.PlotWidget(axisItems={'bottom': axis(orientation='bottom')})
			#pw.getAxis('left').setTickSpacing(1, 0.5)
			if i > 0:
				pw.setXLink(self.trendsPw[0])
			pw.getViewBox().setMouseMode(pw.getViewBox().RectMode) # one button mode
			pw.showGrid(x=True, y=True)
			splitter1.addWidget(pw)
			self.trendsPw.append(pw)

		for i in parameters:
			self.trendsPw[parameters[i].plotid].setLabel('left', text=parameters[i].name, units=parameters[i].unit)

		# elements in the right part of the screen
		right_layout = QVBoxLayout()

		self.c_frames = {}
		self.c_names = {}
		self.c_units = {}
		self.c_limits = {}
		self.c_values = {}
		self.c_infos = {}

		def mkQLabel(objectName, text='', alignment=Qt.AlignLeft):
			o = QLabel()
			o.setObjectName(objectName)
			o.setAlignment(alignment)
			o.setText(text)
			return o

		for i in range(len(parameters)):
			self.c_frames[i] = QGroupBox()
			self.setFrameStyleSheet(i)
			self.c_frames[i].setFlat(True);
			vbox = QVBoxLayout(self.c_frames[i])
			vbox.setSpacing(0)

			self.c_names[i]  = mkQLabel('c_names', parameters[i].name, Qt.AlignLeft | Qt.AlignTop)
			self.c_units[i]  = mkQLabel('c_units', parameters[i].unit, Qt.AlignRight | Qt.AlignTop)
			self.c_limits[i] = mkQLabel('c_limits', str(parameters[i].min)+"-"+str(parameters[i].max), Qt.AlignRight | Qt.AlignTop)
			self.c_values[i] = mkQLabel('c_values', '-', Qt.AlignRight | Qt.AlignTop)
			self.c_infos[i]  = mkQLabel('c_infos', parameters[i].info)

			hbox = QHBoxLayout()
			hbox.addWidget(self.c_names[i])

			vbox2 = QVBoxLayout()
			vbox2.addWidget(self.c_units[i])
			vbox2.addWidget(self.c_limits[i])
			hbox.addLayout(vbox2)

			vbox.addLayout(hbox)
			vbox.addWidget(self.c_values[i])
			vbox.addWidget(self.c_infos[i])
			right_layout.addWidget(self.c_frames[i])

		right_layout.addStretch()

		def makeButton(text, function):
			btn = QPushButton(text)
			btn.setFocusPolicy(Qt.TabFocus)
			btn.clicked.connect(function)
			return btn

		# buttons
		right_layout.addWidget(makeButton("Clear plots", self.btnReset))
		right_layout.addWidget(makeButton("Autorange", self.btnAutoRange))
		right_layout.addWidget(makeButton("Full/Window", self.btnFullScreen))
		right_layout.addWidget(makeButton("Exit", self.close))

		# clock
		timeLabel = QLabel("Time")
		timeLabel.setObjectName('clockLabel')
		self.clockLabel = QLabel("--:--:--")
		self.clockLabel.setObjectName('clock')
		self.clockLabel.setAlignment(Qt.AlignRight)
		gb = QGroupBox()
		gb.setFlat(True);
		gb.setObjectName('clock')
		ly = QVBoxLayout(gb)
		ly.addWidget(timeLabel)
		ly.addWidget(self.clockLabel)
		right_layout.addWidget(gb)

		## entire screen
		container_layout = QHBoxLayout(self)
		container_layout.addLayout(left_layout)
		container_layout.addLayout(right_layout)

		## Display the widget as a new window
		self.setWindowTitle(u"Monitoring")
		self.setWindowState(self.windowState() ^ Qt.WindowMaximized)
		self.showFullScreen()
		self.show()
		self.setCursor(Qt.BlankCursor)

		# Timers
		self.timerHideMouse = QTimer()
		self.timerHideMouse.timeout.connect(self.timerHideMouseTimeout)

		self.timerUpdateUi = QTimer()
		self.timerUpdateUi.timeout.connect(self.timerUpdateUiTimeout)

		self.timerClock = QTimer()
		self.timerClock.timeout.connect(self.timerClockTimeout)
		self.timerClockTimeout()

		# Start timers
		self.timerUpdateUi.start(50)
		self.timerClock.start(1000)
		self.trends_time_ref = time.time()

	def timerUpdateUiTimeout(self):
		global beat
		if (self.div_refresh_values > 0):
			self.div_refresh_values-=1
		if (self.div_refresh_values <= 0):
			self.div_refresh_values=5

			if beat:
				# ~ parameters[PR].info = parameters[PR].info + u'❤'
				parameters[PR].info = u'❤'
				beat=False

			for i in range(len(parameters)):
				self.c_values[i].setText(parameters[i].getValueStr())
				self.c_infos[i].setText(parameters[i].info)
				self.setFrameStyleSheet(i)

			if (time.time() > self.last_graphed_time+2):
				self.last_graphed_time = time.time()

				# update trends
				self.trends_time.append(time.time() - self.trends_time_ref)
				for i in range(len(parameters)):
					parameters[i].copyValueToTrends()

				for pw in self.trendsPw:
					pw.clear()

				for i in range(len(parameters)):
					self.trendsPw[parameters[i].plotid].plot(self.trends_time, parameters[i].trends, pen=parameters[i].color, connect='finite')

		global X_fast_oximeter, Y_fast_oximeter, Y_fast_oximeter_index
		self.oximeter.plot(X_fast_oximeter, Y_fast_oximeter, clear=True, pen=parameters[SPO2].color, connect='finite')

	def setFrameStyleSheet(self, i):
		if math.isnan(parameters[i].value):
			self.c_frames[i].setStyleSheet("QGroupBox { border: 1px solid %s; border-radius: 8px; } QLabel { color: #555555; background-color: transparent; }" % (parameters[i].color));
		elif (parameters[i].value < parameters[i].min or parameters[i].value > parameters[i].max):
			self.c_frames[i].setStyleSheet("QGroupBox { border: 4px solid %s; border-radius: 8px; background-color: #ff0000; } QLabel { color: #000000; background-color: transparent; }" % parameters[i].color);
		else:
			self.c_frames[i].setStyleSheet("QGroupBox { border: 1px solid %s; border-radius: 8px; } QLabel { color: %s; }" % (parameters[i].color, parameters[i].color));

	def keyPressEvent(self, event):
		if (event.key() ==  Qt.Key_F11):
			self.btnFullScreen()
		else:
			event.accept()

	def eventFilter(self, source, event):
		if event.type() == QEvent.MouseMove:
			if event.buttons() == Qt.NoButton:
				self.setCursor(Qt.ArrowCursor)
				self.timerHideMouse.start(750)
			#pos = event.pos()
			#buttons = event.buttons()
			#print('x: %d, y: %d' % (pos.x(), pos.y()), int(buttons))
		return QMainWindow.eventFilter(self, source, event)

	def btnFullScreen(self):
		if (self.isFullScreen()):
			self.showNormal()
			#self.setCursor(Qt.ArrowCursor)
		else:
			self.showFullScreen()
			#self.setCursor(Qt.BlankCursor)
			self.timerHideMouse.start(100)

	def timerHideMouseTimeout(self):
		self.timerHideMouse.stop()
		if (self.isFullScreen()):
			self.setCursor(Qt.BlankCursor)

	def timerClockTimeout(self):
		val = time.strftime("%H:%M:%S", time.localtime(time.time()))
		self.clockLabel.setText(val)

	def btnReset(self):
		self.trends_time = []
		self.trends_time_ref = time.time()
		for i in range(len(parameters)):
			parameters[i].trends = []
		self.last_graphed_time = 0

	def btnAutoRange(self):
		for pw in self.trendsPw:
			pw.enableAutoRange()

	def closeEvent(self, event):
		event.accept();return; # this line is overriding the confirmation

		reply = QMessageBox.question(self, "Confirmation", "Are you sure to quit?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
		if reply == QMessageBox.Yes:
			event.accept()
		else:
			event.ignore()

class DateAxis(pyqtgraph.AxisItem):
	lastString = ""

	def tickStrings(self, values, scale, spacing):
		if len(values) > 1:
			rng = max(values)-min(values)
			if rng < 3600*24:
				string = '%H:%M:%S'
			elif rng >= 3600*24 and rng < 3600*24*30:
				string = '%H:%M:%S\n%Y-%m-%d'
			elif rng >= 3600*24*30 and rng < 3600*24*30*24:
				string = '%Y-%m-%d'
			elif rng >=3600*24*30*24:
				string = '%Y'
			self.lastString = string
		else:
			string = self.lastString

		strns = []
		for value in values:
			try:
				# pyqtgraph seems to don't handle so large numbers on raspberry pi so we're using a reference
				strns.append(time.strftime(string, time.localtime(value + m1.trends_time_ref)))
			except ValueError:  ## Windows can't handle dates before 1970
				strns.append('')
		return strns

class DummyAxis(pyqtgraph.AxisItem):
	def __init__(self, orientation):
		super(DummyAxis, self).__init__(orientation)
		self.setHeight(0)

	def tickStrings(self, values, scale, spacing):
		return ''

def main():
	global m1, oxi1
	app = QApplication(sys.argv)
	m1 = MonitorGUI()

	oxi1 = usb_oximeter.Oximeter()
	oxi1.assignSerialPorts(("/dev/ttyUSB0", "/dev/ttyUSB1"))
	oxi1.setCallback(OximeterCallback)

	threads = []
	threads.append(threading.Thread(target=oxi1.worker))
	threads[0].daemon = True
	threads[0].start()

	m1.last_graphed_time = 0
	app.installEventFilter(m1)
	ret = app.exec_()
	oxi1.stop()
	sys.exit(ret)

if __name__ == '__main__':
	main()
