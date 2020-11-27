# UPDATED: 11/18/2020

# File: sender.py

# Contains:
#   Class
#	Sender class - The Sender class sends the camera feed over UDP.
#   Functions
#	get_pipeline() - Gst launch commands in a string for different cameras on the TX2
#	run() - to run the pipelines


import sys
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject, GLib
from time import sleep

class Sender():
	def __init__(self, pipeline):
		self.running = False
		self.pipeline = None
		self.launch_pipeline(pipeline)
		#self.play()

	def play(self):
		self.running = True
		stream = self.pipeline.set_state(Gst.State.PLAYING)
		print('Set to playing')
		if stream ==  Gst.StateChangeReturn.FAILURE:
			print('ERROR: Unable to set the pipeline to the playing state')

	def pause(self):
		self.running = False
		stream = self.pipeline.set_state(Gst.State.PAUSE)
		print('Pipeline paused')
		if stream == Gst.StateChangeReturn.FAILURE:
			print('ERROR: Unable to set pipeline to paused state')

	def launch_pipeline(self, pipeline):
		self.pipeline = Gst.parse_launch(pipeline)
		bus = self.pipeline.get_bus()
		bus.add_signal_watch()
		bus.connect('message', self.on_message)
		global ref
		ref+=1

	def on_message(self, bus, message):
		t = message.type
		if t == Gst.MessageType.ERROR:
			err, dbg = message.parse_error()
			print('ERROR:', message.src.get_name(), ':', err.message)
			print('debugging info:', dbg)
			self._shutdown()
		elif t == Gst.MessageType.EOS:
			print('End-Of-Stream reached')
			self._shutdown()
		else:
		       pass#print('ERROR: Unexpected message received')
		return True

	def _shutdown(self):
		print('Shutting down pipeline')
		self.pipeline.bus.remove_signal_watch()
		self.pipeline.set_state(Gst.State.NULL)
		global ref
		ref-=1


def get_pipeline(machine=None, cam=None, ip='192.168.2.0', port='8080'):
	if machine == 'tx2':
		if cam == 'cam2':
			device_n_caps = ('v4l2src device=/dev/video1 ! '
					'video/x-raw, framerate=30/1, width=640, height=480 ! '
					)
		elif cam == 'cam3':	#Stereo Vision 1 (usb-3530000.xhci-2.3)
			device_n_caps = ('v4l2src device=/dev/video3 ! '
					'video/x-raw, format=YUY2, width=640, height=480 ! '
					)
		elif cam == 'cam4':	#HD USB Camera (usb-3530000.xhci-2.4)
			device_n_caps = ('v4l2src device=/dev/video4 ! '
					'video/x-raw, width=640, height=480 ! ')

	elif machine == 'file':
		if cam == "": cam = 'testvideo0'
		device_n_caps = ('filesrc location=' + cam + '.raw ! videoparse format=4 '
				 'width=640 height=480 framerate=30/1 ! ')

	if device_n_caps is None:
		device_n_caps = 'videotestsrc ! '

	return (device_n_caps +
		'videoscale ! video/x-raw, width=480, height=360 ! '
		'nvvidconv ! '
		'omxh265enc ! '
		'h265parse ! '
		'rtph265pay ! '
		'udpsink host=' + ip + ' port=' + port)


def run():
	GObject.threads_init()
	Gst.init(None)

	#pipe = get_pipeline('file', 'testvideo1', port='8080')
	pipe = get_pipeline('tx2', 'cam2', port='8080')
	cam = Sender(pipe)
	cam.play()

	#pipe2 = get_pipeline('file', 'testvideo0', port='8081')
	pipe2 = get_pipeline('tx2', 'cam3', port='8081')
	cam2 = Sender(pipe2)
	cam2.play()

	pipe3 = get_pipeline('file', 'testvideo2', port='8082')
	#pipe3 = get_pipeline('tx2', 'cam4', port='8082')
	cam3 = Sender(pipe3)
	cam3.play()

	GLib.MainLoop().run()
	#while ref>0: sleep(0.5)


if __name__=="__main__":
	ref=0
	run()
