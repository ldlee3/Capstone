# UPDATED: 11/18/2020

# File: sender.py

# Contains:
#   Class
#	Sender class - The Sender class sends the camera feed over UDP.
#   Functions
#	get_pipeline() - Gst launch commands in a string for different cameras on the TX2
#	run() - to run the pipelines


import sys
import socket
import threading
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
		stream = self.pipeline.set_state(Gst.State.NULL)#PAUSED)
		print('Pipeline paused')
		if stream == Gst.StateChangeReturn.FAILURE:
			print('ERROR: Unable to set pipeline to paused state')


	def launch_pipeline(self, pipeline):
		self.pipeline = Gst.parse_launch(pipeline)
		bus = self.pipeline.get_bus()
		bus.add_signal_watch()
		bus.connect('message', self.on_message)


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
		       print('ERROR: Unexpected message received')
		return True


	def _shutdown(self):
		print('Shutting down pipeline')
		self.pipeline.bus.remove_signal_watch()
		self.pipeline.set_state(Gst.State.NULL)


def get_pipeline(machine=None, cam=None, ip="127.0.0.1", port='8080'):
	if machine == 'tx2':
		if cam == 'cam1':
			device_n_caps = ('v4l2src device=/dev/video1 ! '
					'video/x-raw, framerate=30/1, width=640, height=480 ! ')
		elif cam == 'cam2':	#Stereo Vision 1 (usb-3530000.xhci-2.3)
			device_n_caps = ('v4l2src device=/dev/video3 ! '
					'video/x-raw, format=YUY2, width=640, height=480 ! ')
		elif cam == 'cam3':	#HD USB Camera (usb-3530000.xhci-2.4)
			device_n_caps = ('v4l2src device=/dev/video4 ! '
					'video/x-raw, width=640, height=480 ! ')

	elif machine == 'file':
		if cam == "": cam = 'testvideo0'
		device_n_caps = ('filesrc location=' + cam + '.raw ! videoparse format=4 '
				 'width=640 height=480 framerate=30/1 ! ')

	if device_n_caps is None:
		device_n_caps = 'videotestsrc ! '

	return (device_n_caps +
		'nvvidconv ! '
		'omxh265enc iframeinterval=5 ! '
		'rtph265pay ! '
		'udpsink host=' + ip + ' port=' + port)

def sserv_loop():
	global camv
	print("control server up")
	while True:
		try: cli,addr=ssock.accept()
		except: break
		dat=b''
		while not dat.endswith(b'\n'):
			dtt=cli.recv(64)
			if dtt==b'': break
			else: dat+=dtt
		cli.close()
		dat=dat.strip(b'\n').decode("ascii")
		if dat=="STOP": break
		dat=dat.split(' ')
		if len(dat)==2 and dat[0] in camv:
			if dat[1]=="up" and not camv[dat[0]].running: camv[dat[0]].play()
			elif dat[1]=="down" and camv[dat[0]].running: camv[dat[0]].pause()
	print("control server down")
	ssock.close()

def sserv_init(ip,port):
	global ssock,sthread
	ssock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	ssock.bind((ip,port))
	ssock.listen()
	sthread=threading.Thread(target=sserv_loop)
	sthread.start()

def sserv_stop():
	global ssock,sthread
	if sthread.is_alive():
		tsock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
		tsock.connect(ssock.getsockname())
		tsock.send(b'STOP\n')
		tsock.close()
		sthread.join()

def run():
	ip="192.168.2.0"
	
	GObject.threads_init()
	Gst.init(None)
	
	global camv
	camv={}
	camv["cam1"]=Sender(get_pipeline('tx2', 'cam1', ip=ip, port='8080'))
	camv["cam2"]=Sender(get_pipeline('tx2', 'cam2', ip=ip, port='8081'))
	camv["cam3"]=Sender(get_pipeline('tx2', 'cam3', ip=ip, port='8082'))
	#for c in camv: camv[c].play()
	
	sserv_init(ip,9990)
	
	try: GLib.MainLoop().run()
	except KeyboardInterrupt: pass
	
	sserv_stop()

if __name__=="__main__": run()
