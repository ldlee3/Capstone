
# UPDATED: 10/18/2020

# This program runs a Gstreamer pipeline using /dev/video2 as a src
# and send the live cast to opencv, which scans each frame for a QR code.
# If a QR Code is detected, it will outline the QR Code in purple and
# display the decoded string above the QR Code. It then sends these frames
# over udp to ip: 192.168.2.0 port: 8080. Use the pipeline below.

# Receiving Pipeline:
#  gst-launch-1.0 udpsrc address=192.168.2.0 port=8080 ! \
#  application/x-rtp, encoding-name=H265, payload=96 ! rtph265depay ! \
#  h265parse ! queue ! omxh265dec ! nvvidconv ! ximagesink



import sys
#import threading
import numpy as np
import cv2
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib, GObject
from pyzbar.pyzbar import decode #for QR (and bar) code detection

#GObject.threads_init()
Gst.init(None)


class GstPipeline:
	def __init__(self, pipeline):
		self.frame = None
		self.running = False
		self.pipeline = Gst.parse_launch(pipeline)
		self.video_sink = None

		bus = self.pipeline.get_bus()
		bus.add_signal_watch()
		bus.connect('message', self.on_message)
		self.play()

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
		#else:
		#	print('ERROR: Unexpected message received')
		return True


	def _shutdown(self):
		self.pipeline.bus.remove_signal_watch()
		self.pipeline.set_state(Gst.State.NULL)


	def play(self):
		self.running = True
		stream = self.pipeline.set_state(Gst.State.PLAYING)
		if stream ==  Gst.StateChangeReturn.FAILURE:
			print('ERROR: Unable to set the pipeline to the playing state')
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
	elif machine == 'rasppi':
		if cam == 'cam0':
			pass
		elif cam == 'cam4':
			pass

	else: device_n_caps = 'videotestsrc ! '

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



if __name__ == '__main__':

	cam_pipe = get_pipeline('tx2', 'cam2')
	cam = GstPipeline(cam_pipe)

	out = cv2.VideoWriter(get_pipeline_out(), 1, 30.0, (640,480), True)

	if not out.isOpened():
		print('videowriter not open')

	while True:
		# Wait for the next frame
		if not cam.frame_available():
			continue

		frame = cam.get_frame()
		for qr_code in decode(frame):
			myData = qr_code.data.decode('utf-8')
			print(myData)
			pts = np.array([qr_code.polygon], np.int32)
			pts = pts.reshape((-1,1,2))
			cv2.polylines(frame, [pts], True, (255, 0, 255), 5) #box around qr code
			# uncomment below 2 for decoded QR string to appear above QR Code
			#pts2 = qr_code.rect
			#cv2.putText(frame, myData, (pts2[0], pts2[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,0,255), 2)

		out.write(frame)
		cv2.imshow('frame', frame)

		if cv2.waitKey(1) & 0xFF == ord('q'):
			break

	cam.release()
	out.release()
