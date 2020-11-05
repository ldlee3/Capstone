# UPDATED: 10/21/2020

# File: sender.py

# Contains:
#   Class
#	Sender class - inherits from class GstPipeline. The Sender class handles
#	the stream from the cameras and sends them to appsink (OpenCV).
#   Functions
#	get_pipeline() - Gst launch commands in a string for different cameras on the TX2
#	get_pipeline_out() - Gst launch command to send from OpenCV to udpsink using
#	ip 192.168.2.0 and port 8080


import sys
import numpy as np
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import pipeline as p


class Sender(p.GstPipeline):
	def __init__(self, pipeline):
		super().__init__()
		super().launch_pipeline(pipeline)
		super().play()
		self.video_sink = None
		self.connect_sink()


	def connect_sink(self):
		self.video_sink = self.pipeline.get_by_name('appsink0')
		self.video_sink.connect('new-sample', self.callback)


	def callback(self, sink):
		sample = sink.emit('pull-sample')
		new_frame = self.gst_to_opencv(sample)
		self.frame = new_frame
		return Gst.FlowReturn.OK


	def gst_to_opencv(self, sample):
		buff = sample.get_buffer()
		caps = sample.get_caps()
		array = np.ndarray(
			(
				caps.get_structure(0).get_value('height'),
				caps.get_structure(0).get_value('width'),
				3
			),
			buffer=buff.extract_dup(0, buff.get_size()), dtype=np.uint8)
		return array


	def get_frame(self):
		return self.frame 	 #cap.read() output


	def frame_available(self):
		return type(self.frame) != type(None)


def get_pipeline(machine="", cam=''):

	if machine == 'tx2':
		if cam == 'cam2':	#HD USB Camera (usb-3530000.xhci-2.2)
			device_n_caps = (
					'v4l2src device=/dev/video2 ! '
					'video/x-h264, framerate=30/1, width=640, height=480 ! '
					'omxh264dec !'
					)
		elif cam == 'cam3':	#Stereo Vision 1 (usb-3530000.xhci-2.3)
			device_n_caps = (
					'v4l2src device=/dev/video3 ! '
					'video/x-raw, format=YUY2, width=640, height=480 ! '
					)
		elif cam == 'cam4':	#HD USB Camera (usb-3530000.xhci-2.4)
			device_n_caps = (
					'v4l2src device=/dev/video4 ! '
					'video/x-raw, width=640, height=480 ! '
					)

	elif machine == 'file':
		device_n_caps = ('filesrc location=testvideo0.raw ! videoparse format=4 '
			'width=640 height=480 framerate=30/1 ! ')

	if device_n_caps is None:
		device_n_caps = 'videotestsrc ! '

	return (
		device_n_caps + 'videoconvert ! '
		'video/x-raw, format=(string){RGB} ! '
		'appsink emit-signals=true max-buffers=1 drop=true'
	)


def get_pipeline_out():
	ip = '192.168.2.0'
	port = '8080'
	return (
		"appsrc ! "
		"video/x-raw, format=BGR ! "
		"queue ! "
		"videoconvert ! "
		"video/x-raw, format=BGRx ! "
		"nvvidconv ! "
		"omxh265enc ! "
		"video/x-h265, stream-format=byte-stream ! "
		"h265parse ! "
		"rtph265pay pt=96 config-interval=1 ! "
		"udpsink host=" + ip + " port=" + port
	)
