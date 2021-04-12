#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# sudo apt-get install python3-pip python3-setuptools python3-pyqtgraph
# python3 -m pip install --upgrade pip
# python3 -m pip install --upgrade pyserial
# python3 -m pip install pyqt5==5.13.0
# use this pyqt5 version if there is graph is some points are NaN (5.14.1 was bugged)

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
	from PyQt5.QtGui import *
	from PyQt5.QtCore import *
	from PyQt5.QtWidgets import *
	print("*** Using PyQT5 ***")
except:
	try:
		from PyQt4.QtGui import *
		from PyQt4.QtCore import *
		print("*** Using PyQT4 ***")
	except:
		pipInstall("pyqt5")

try:
	import numpy
except:
	pipInstall("numpy")

try:
	import pyqtgraph # import PyQt4 or 5 before this line!
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

tracesTimeRef = time.time()
class Trace():
	def __init__(self, ident, color):
		self.ident = ident
		self.color = color
		self.traceT = []
		self.traceX = []
		self.traceY = []
		self.pw = None

	def createWidget(self):
		self.pw = pyqtgraph.PlotWidget()
		self.pw.showAxis('bottom', show=False)
		self.pw.showAxis('left', show=False)
		self.pw.setMouseEnabled(False, False)
		self.pw.setXRange(0, 10, padding=0)
		# ~ self.pw = QLabel()
		self.pw.setStyleSheet("background-color: red")
		self.pw.setContentsMargins(0,0,0,0);
		self.update()

	def addPoint(self, waveformValue):
		"""function to be called by plugins in another thread than the main thread"""
		now = time.time()

		self.traceT.append(now)
		self.traceX.append(now - tracesTimeRef)
		self.traceY.append(waveformValue)
		self.updateFlag = True

	def update(self):
		try:
			while self.traceT[0] <= time.time()-9.9:
				del self.traceT[0]
				del self.traceX[0]
				del self.traceY[0]
		except:
			pass

		self.pw.plot(self.traceX, self.traceY, clear=True, pen=self.color, connect='finite')
		self.updateFlag = False

class TracesSet():
	def __init__(self):
		self.traces = {}

	def initialyzeWidgets(self):
		self.tracesSplitter = QSplitter(Qt.Vertical)
		self.tracesSplitter.addWidget(QLabel("UNINITIALIZED TRACES SET!"))

	def generateTracesPlots(self):
		# delete everything existing in the tracesSet qsplitter
		for i in range(self.tracesSplitter.count()):
			self.tracesSplitter.widget(i).deleteLater()

		# then (re)create the plotwidgets
		for ident in self.traces:
			trace = self.traces[ident]
			trace.createWidget()
			self.tracesSplitter.addWidget(trace.pw)

	def addTrace(self, ident, *kargs, **kwargs):
		print("Adding trace", ident)
		self.traces[ident] = Trace(ident, *kargs, **kwargs)
		return self.traces[ident]

	def update(self):
		global tracesTimeRef, tracesClearModeFlag
		if time.time() - tracesTimeRef > 10:
			for ident in self.traces:
				self.traces[ident].addPoint(float('nan'))
			tracesTimeRef = time.time()

		for ident in self.traces:
			trace = self.traces[ident]
			if trace.updateFlag:
				trace.update()

	def removeTrace(self, ident):
		del self.traces[ident]

class Parameter():
	NO_SIGNAL = 1
	ALARM     = 2
	NOMINAL   = 3
	DEFAULT   = -1

	def __init__(self, ident, name, unit, plotName, color, format, vmin, vmax):
		self.ident = ident
		self.nextRefresh = 0
		self.name = name
		self.plotName = plotName
		self.unit = unit
		self.color = color
		self.format = format
		self.value = float("nan")
		self.min = vmin
		self.max = vmax
		self.plotId = None
		self.frameState = self.DEFAULT
		self.info = ""
		self.trends = []
		print("Created parameter:", name)

	def __del__(self):
		print("Deleted parameter:", self.name)

	def updateFrameStyleSheet(self, force=False):
		if math.isnan(self.value):  newState = self.NO_SIGNAL
		elif self.value < self.min: newState = self.ALARM
		elif self.value > self.max: newState = self.ALARM
		else:                       newState = self.NOMINAL

		if newState != self.frameState or force:
			if force:
				self.frameState = self.DEFAULT
			else:
				self.frameState = newState

			if newState == self.NO_SIGNAL:
				styleStr = "QGroupBox { border: 1px solid $PARAMCOLOR; } QLabel { color: #555555; background-color: transparent; }"
			elif newState == self.ALARM:
				styleStr = "QGroupBox { border: 4px solid $PARAMCOLOR; background-color: #ff0000; } QLabel { color: #000000; background-color: transparent; }"
			elif newState == self.NOMINAL:
				styleStr = "QGroupBox { border: 1px solid $PARAMCOLOR; } QLabel { color: $PARAMCOLOR; }"
			else:
				styleStr = ""

			self.widget.setStyleSheet(styleStr.replace("$PARAMCOLOR", self.color))

	def createWidgets(self):
		class QValueLabel(QLabel):
			def sizeHint(self):
				return super(QValueLabel, self).sizeHint() + QSize(0, -14)
			def minimumSizeHint(self):
				return super(QValueLabel, self).minimumSizeHint() + QSize(0, -14)

		def mkQLabel(objectName, text='', alignment=Qt.AlignLeft, o=None):
			if o is None:
				o=QLabel()
			o.setObjectName(objectName)
			o.setAlignment(alignment)
			o.setText(text)
			return o

		self.widget = QGroupBox()
		self.widget.setFlat(True);
		vbox = QVBoxLayout(self.widget)
		vbox.setSpacing(0)
		vbox.setContentsMargins(4, 2, 4, 2)

		self.nameLabel   = mkQLabel('names', self.name, Qt.AlignLeft | Qt.AlignTop)
		self.unitLabel   = mkQLabel('units', self.unit, Qt.AlignRight | Qt.AlignTop)
		self.limitsLabel = mkQLabel('limits', str(self.min)+"-"+str(self.max), Qt.AlignRight | Qt.AlignTop)
		self.valueLabel  = mkQLabel('values', '---', Qt.AlignRight | Qt.AlignTop, QValueLabel())
		self.infosLabel  = mkQLabel('infos', '')

		# fix the height of infosLabel widget (we don't want it to vary later)
		height = self.infosLabel.sizeHint().height()
		self.infosLabel.setFixedHeight(int(height*1.6))

		hbox = QHBoxLayout()
		hbox.addWidget(self.nameLabel)

		vbox2 = QVBoxLayout()
		vbox2.addWidget(self.unitLabel)
		vbox2.addWidget(self.limitsLabel)
		hbox.addLayout(vbox2)

		vbox.addLayout(hbox)
		vbox.addWidget(self.valueLabel)
		vbox.addWidget(self.infosLabel)
		self.updateFrameStyleSheet(force=True)

	def updateValue(self, value):
		if value != self.value:
			self.value = value

	def updateWidgets(self):
		self.valueLabel.setText(self.getValueStr())
		self.infosLabel.setText(self.info)
		self.updateFrameStyleSheet()

	def copyValueToTrends(self):
		self.trends.append(self.value)

	def getValueStr(self):
		if (self.value != self.value):
			return('---')
		else:
			return(self.format % self.value)

class ParametersSet():
	def __init__(self):
		self.trends_time_ref = time.time()
		self.parameters = {}

	def initialyzeWidgets(self):
		self.numericLayout = QVBoxLayout()
		self.trendsSplitter = QSplitter(Qt.Vertical)
		self.plots = {}
		self.trendsPw = []

	def generateTrendsPlots(self):
		for pw in self.trendsPw:
			pw.deleteLater()
			del pw

		plotCntr = 0
		plotsNames = {}
		for p in self.parameters:
			try:
				self.parameters[p].plotId = plotsNames[self.parameters[p].unit]
			except:
				plotsNames[self.parameters[p].unit] = plotCntr
				self.parameters[p].plotId = plotCntr
				plotCntr+=1

		self.trends_time = []
		self.trendsPw = []
		first = True
		for plotName in plotsNames:
			axis = DummyAxis
			if len(self.trendsPw) == len(plotsNames)-1: axis = DateAxis
			pw = pyqtgraph.PlotWidget(axisItems={'bottom': axis(orientation='bottom')})
			if not first:
				pw.setXLink(self.trendsPw[0])
			pw.getViewBox().setMouseMode(pw.getViewBox().RectMode) # one button mode
			pw.getAxis('left').setWidth(50)
			pw.showGrid(x=True, y=True)
			self.trendsSplitter.addWidget(pw)
			self.trendsPw.append(pw)
			first=False

		for p in self.parameters:
			self.trendsPw[self.parameters[p].plotId].setLabel('left', text=self.parameters[p].plotName, units=self.parameters[p].unit)

	def updateTrends(self):
		self.trends_time.append(time.time() - self.trends_time_ref)
		for p in self.parameters:
			self.parameters[p].copyValueToTrends()

		for pw in self.trendsPw:
			pw.clear()

		for p in self.parameters:
			pw = self.trendsPw[self.parameters[p].plotId]
			pw.plot(self.trends_time, self.parameters[p].trends, pen=self.parameters[p].color, connect='finite', clear=False)

	def addParameter(self, ident, *kargs, **kwargs):
		print("adding", ident)
		self.parameters[ident] = parameter = Parameter(ident, *kargs, **kwargs)
		parameter.createWidgets()
		self.numericLayout.addWidget(parameter.widget)
		return self.parameters[ident]

	def updateParametersWidgets(self):
		for ident in self.parameters:
			parameter = self.parameters[ident]
			if parameter.nextRefresh <= time.time():
				parameter.updateWidgets()
				parameter.nextRefresh = time.time() + 0.2

	def removeParameter(self, ident):
		self.numericLayout.removeWidget(self.parameters[ident].widget)
		del self.parameters[ident]

class Plugin():
	def __init__(self, name):
		print("Loading plugin:", name)
		self.name = name

		try:
			self.module = __import__("%s" % self.name)
		except Exception as e:
			self.module = None
			print('PLUGIN ERROR (%s): %s' % (self.name, e))

	def load(self):
		try:
			self.PluginClass = self.module.MonitorPlugin(parametersSet, tracesSet)
			self.PluginClass.load()
		except Exception as e:
			print('PLUGIN ERROR (%s): %s' % (self.name, e))
	def unload(self):
		try:
			self.PluginClass.unload()
		except Exception as e:
			print('PLUGIN ERROR (%s): %s' % (self.name, e))

class PluginManager():
	def __init__(self):
		self.plugins = {}
		for filename in os.listdir(os.path.dirname(os.path.abspath(__file__))):
			if filename.endswith("_plugin.py"):
				if filename.endswith(".py"):
					name = filename[:len(filename)-3]
					self.plugins[name] = Plugin(name)

	def loadEverything(self):
		for name in self.plugins:
			self.plugins[name].load()

	def __del__(self):
		for name in self.plugins:
			self.plugins[name].unload()

tracesSet = TracesSet()
parametersSet = ParametersSet()
pluginManager = PluginManager()

class MonitorGUI(QWidget):
	def __init__(self):
		super(MonitorGUI, self).__init__()
		self.trends_time = []
		self.last_graphed_time = 0

		tracesSet.initialyzeWidgets()
		parametersSet.initialyzeWidgets()
		pluginManager.loadEverything()

		tracesSet.generateTracesPlots()
		parametersSet.generateTrendsPlots()

		self.initUI()

	def initUI(self):
		self.setStyleSheet("\
			QWidget { background-color: #000000; color: #ffffff; } \
			QLabel { margin: 0px; padding-top: 0px; padding-bottom: 0px; } \
			QSplitter::handle:vertical   { image: none; } \
			QSplitter::handle:horizontal { width:  2px; image: none; } \
			QPushButton { background-color: #404040; background: #404040; } \
			QLabel#names { font-size: 30pt; } \
			QLabel#units { font-size: 20pt; } \
			QLabel#limits { font-size: 10pt; } \
			QLabel#values { font-size: 80pt; } \
			QLabel#infos { font-size: 15pt; } \
			QLabel#clockLabel { color: #707070; font-size: 10pt; } \
			QLabel#clock { font-size: 15pt; } \
			QGroupBox { border: 1px solid #707070; border-radius: 8px; padding: 0px; }\
			QLayout {padding-top: 100px; }\
		");

		# elements in the left part of the screen
		self.allCurvesSplitter = QSplitter(Qt.Vertical)
		self.allCurvesSplitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

		# pyqtgraph curves
		self.allCurvesSplitter.addWidget(tracesSet.tracesSplitter)
		self.allCurvesSplitter.addWidget(parametersSet.trendsSplitter)

		# elements in the right part of the screen
		right_layout = QVBoxLayout()
		right_layout.addLayout(parametersSet.numericLayout)
		right_layout.addStretch()

		def makeButton(text, function):
			btn = QPushButton(text)
			btn.setFocusPolicy(Qt.TabFocus)
			btn.clicked.connect(function)
			return btn

		# buttons
		self.buttons = []
		self.buttons.append(makeButton("Clear plots", self.btnReset))
		self.buttons.append(makeButton("Autorange", self.btnAutoRange))
		self.buttons.append(makeButton("Full/Window", self.btnFullScreen))
		self.buttons.append(makeButton("Exit", self.close))

		for btn in self.buttons:
			right_layout.addWidget(btn)

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
		ly.setSpacing(0)
		ly.setContentsMargins(4, 2, 4, 2)
		ly.addWidget(timeLabel)
		ly.addWidget(self.clockLabel)
		right_layout.addWidget(gb)

		## entire screen
		container_layout = QHBoxLayout(self)
		container_layout.addWidget(self.allCurvesSplitter)
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

	def timerUpdateUiTimeout(self):
		tracesSet.update()
		parametersSet.updateParametersWidgets()

		if (time.time() > self.last_graphed_time+2):
			self.last_graphed_time = time.time()

			# update trends
			parametersSet.updateTrends()

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
		for pw in parametersSet.trendsPw:
			pw.clear()
		parametersSet.trends_time = []
		parametersSet.trends_time_ref = time.time()
		for p in parametersSet.parameters:
			parametersSet.parameters[p].trends = []
		self.last_graphed_time = 0

	def btnAutoRange(self):
		for pw in parametersSet.trendsPw:
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
				strns.append(time.strftime(string, time.localtime(value + parametersSet.trends_time_ref)))
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
	app = QApplication(sys.argv)
	m1 = MonitorGUI()
	app.installEventFilter(m1)
	ret = app.exec_()
	sys.exit(ret)

if __name__ == '__main__':
	main()
