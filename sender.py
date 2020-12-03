# UPDATED: 11/18/2020

# File: sender.py

# Contains:
#   Class
#	Sender class - The Sender class sends the camera feed over UDP.
#   Functions
#	get_pipeline() - Gst launch commands in a string for different cameras on the TX2
#	run() - to run the pipelines


import os
import sys
import mmap
import posix_ipc
import numpy as np
import cv2
import socket
import threading
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject, GLib
from time import sleep

import traceback

buf_w=1280
buf_h=720
buf_d=4
buf_sz=buf_w*buf_h*buf_d

upcroot="/home/nvidia/roverupc/"

shm2cmdname={
	"shm_zedleft":b"left",
	"shm_zedright":b"right",
	"shm_zeddepth":b"depth",
	"shm_cvsobel":b"sobel",
}

#shm_l=posix_ipc.SharedMemory("shm_zedleft",read_only=True)
#memm_l=mmap.mmap(shm_l.fd,buf_sz,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ)
#csock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)

#csock.connect(upcroot+"comm/cvzshare.sock")

#csock.send(b"set left up\0")
#reply=csock.recv(64)
#print(reply)

class Sender():
	def __init__(self, pipeline):
		self.running = False
		self.pipeline = None
		self.launch_pipeline(pipeline)
		#self.play()


	def play(self):
		self.running = True
		stream = self.pipeline.set_state(Gst.State.PLAYING)
		if stream ==  Gst.StateChangeReturn.FAILURE:
			print('ERROR: Unable to set the pipeline to the playing state')
		else: print('Set to playing')


	def pause(self):
		self.running = False
		stream = self.pipeline.set_state(Gst.State.NULL) #PAUSED)
		if stream == Gst.StateChangeReturn.FAILURE:
			print('ERROR: Unable to set pipeline to paused state')
		else: print('Pipeline paused')


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
		       pass #print('ERROR: Unexpected message received')
		return True


	def _shutdown(self):
		print('Shutting down pipeline')
		self.pipeline.bus.remove_signal_watch()
		self.pipeline.set_state(Gst.State.NULL)


class cvzSender(Sender):
	def __init__(self, pipeline, shmname):
		global upcroot,shm2cmdname,buf_sz
		self.shmname=shmname
		self.shm=posix_ipc.SharedMemory(self.shmname,read_only=True)
		self.memm=mmap.mmap(self.shm.fd,buf_sz,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ)
		self.csock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
		self.csock.connect(upcroot+"comm/cvzshare.sock")
		self.csock.send(b"set %s up\0"%shm2cmdname[self.shmname])
		self.lframe=0
		reply=self.csock.recv(64)
		#print(reply)
		super().__init__(pipeline)
	
	def __del__(self):
		print("cvz del")
		self.csock.send(b'set %s down\0'%shm2cmdname[self.shmname])
		reply=self.csock.recv(64)
		self.csock.close()
		self.memm.close()
		self.shm.close_fd()

	def need_data(self, src, len):
		#print('need data')
		self.push(src)


	def push(self, src):
		global buf_sz,shm2cmdname
		#while self.running:
		try:
			self.csock.send(b"read %s lock\0"%shm2cmdname[self.shmname])
			reply=self.csock.recv(64).strip(b'\0').decode("ascii")
			#print(reply)
			fnum=int(reply[4:])
			dat=self.memm.read(buf_sz)
			self.memm.seek(0)
		finally:
			self.csock.send(b"read %s release\0"%shm2cmdname[self.shmname])
			reply=self.csock.recv(64).strip(b'\0').decode("ascii")
			#print(reply)
		try:
			#if fnum!=fnumlast:
			self.lframe=fnum
			#npdat=np.frombuffer(dat,dtype=np.ubyte)
			#frame_l=npdat.reshape(buf_h,buf_w,buf_d)
			frame_l=Gst.Buffer.new_wrapped(dat)
			#fcaps=Gst.Caps.from_string("video/x-raw,format=RGBA,width=1280,height=720")
			#src.emit('push-sample',Gst.Sample(frame_l,fcaps,None,None))
			src.emit('push-buffer',frame_l)
			#print('pushed')
		except:
			pass
			#print('except:')
			traceback.print_exc()
			#break


	def connect_src(self):
		source = self.pipeline.get_by_name('appsrc')
		source.connect('need-data', self.need_data)



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


def get_zed(ip="127.0.0.1", port="8090"):
	return ('appsrc name=appsrc format=3 caps="video/x-raw,width=1280,height=720,format=RGBA" emit-signals=true is-live=true ! '
		'video/x-raw, format=RGBA, width=1280, height=720, framerate=30/1 ! '
		'videoscale ! video/x-raw, width=640, height=480 ! '
		#'ximagesink')
		'nvvidconv ! omxh265enc ! video/x-h265 ! rtph265pay ! '
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
	ssock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
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
	ip="192.168.0.101"

	GObject.threads_init()
	Gst.init(None)
	
	global camv
	camv={}
	camv["cam1"]=Sender(get_pipeline('tx2', 'cam1', ip=ip, port='8080'))
	camv["cam2"]=Sender(get_pipeline('tx2', 'cam2', ip=ip, port='8081'))
	camv["cam3"]=Sender(get_pipeline('tx2', 'cam3', ip=ip, port='8082'))

	zedcam = cvzSender(get_zed(ip=ip, port='8090'),"shm_zedleft")
	zedcam.connect_src()
	camv["camz1"]=zedcam
	zedcam2 = cvzSender(get_zed(ip=ip, port='8091'),"shm_zeddepth")
	zedcam2.connect_src()
	camv["camz2"]=zedcam2
	zedcam3 = cvzSender(get_zed(ip=ip, port='8092'),"shm_cvsobel")
	zedcam3.connect_src()
	camv["camz3"]=zedcam3
	#for c in camv: camv[c].play()
	
	sserv_init(ip,9990)
	
	try: GLib.MainLoop().run()
	except KeyboardInterrupt: pass
	
	sserv_stop()
	
	#csock.send(b'set left down')
	#csock.close()
	#memm_l.close()
	#shm_l.close_fd()

if __name__=="__main__": run()
