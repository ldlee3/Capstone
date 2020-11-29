# UPDATED: 11/8/2020
# CHANGE: added multiple (3) streams and radio buttons to switch between the streams.
#	  Gstreamer input-selector used for switching. The streams are from the same ip
#	  different ports.

# File: receiver.py

# Contains:
#   Class
#	Receiver class - inherits from Gtk.Window, creates a Gtk Window to play the
#	incoming streams played over udp from ip 192.168.2.0 on port 8080-8082. The window
#	includes two buttons, one for capturing images and one for recording video.
#	This is done by linking bins to tees and unlinking when unneeded.
#	The window also includes 3 radio buttons to switch between the 3 streams.
#   Functions
#	get_recv_pipeline() - Gst launch pipeline as a string which receives a stream
#	from a udpsrc and plays it on ximagesink display. There are two tees in the
#	pipeline for hooking in the bins for saving images and videos, and three sources
#	with an input-selector.


'''
Full Receiving Pipeline:
gst-launch-1.0
udpsrc address=192.168.2.0 port=8080 ! selector. !
udpsrc address=192.168.2.0 port=8081 ! selector. !
udpsrc address=192.168.2.0 port=8082 ! selector. !
input-selector name=selector ! application/x-rtp ! rtph265depay !
tee name=t ! queue ! h265parse ! omxh265dec ! tee name=t2 ! queue ! nvvidconv ! ximagesink
t. ! queue ! h265parse ! matroskamux ! filesink location=vidoutput#.mkv async=false
t2. ! queue ! nvvidconv ! jpegenc ! filesink location=imageout#.jpeg async=false
'''


import sys
import socket
import threading
import gi
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')
gi.require_version('GdkX11', '3.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import GObject, Gst, Gtk, GdkX11, GstVideo


class Receiver(Gtk.Window):
	def __init__(self, pipeline):
		# ===== Gtk GUI Setup ===== #
		Gtk.Window.__init__(self, title='Livestream')
		self.connect("destroy", lambda a=None,b=None: self._shutdown())
		self.set_resizable(False)
		self.set_default_size(640, 480)

		# box to hold everything
		vbox = Gtk.VBox()
		vbox.set_border_width(10)
		self.add(vbox)

		# box to hold radio buttons for switching between streams
		self.buttonbox = Gtk.Box()
		vbox.pack_start(self.buttonbox, True, True, 0)

		# area for video player
		self.window = Gtk.DrawingArea()
		self.window.set_size_request(640,480)
		vbox.pack_start(self.window, True, True, 0)

		# radio button for camera 1
		self.cam1_button = Gtk.RadioButton.new_with_label_from_widget(None, 'Camera 1')
		self.cam1_button.connect('toggled', self.on_switch, 'cam1')
		self.buttonbox.add(self.cam1_button)

		# radio button for camera 2
		self.cam2_button = Gtk.RadioButton.new_from_widget(self.cam1_button)
		self.cam2_button.set_label('Camera 2')
		self.cam2_button.connect('toggled', self.on_switch, 'cam2')
		self.buttonbox.add(self.cam2_button)

		# radio button for camera 3
		self.cam3_button = Gtk.RadioButton.new_with_label_from_widget(self.cam1_button, 'Camera 3')
		self.cam3_button.connect('toggled', self.on_switch, 'cam3')
		self.buttonbox.add(self.cam3_button)

		# Add space for capture buttons
		hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
		vbox.pack_start(hbox, False, False, 0)
		hbox.set_border_width(10)

		# Add Recording and Capture buttons
		self.button = Gtk.Button(label="Start Recording")
		self.button.connect("clicked", self.record_button)
		hbox.pack_start(self.button, False, False, 0)
		self.button2 = Gtk.Button(label="Take Snapshot")
		self.button2.connect("clicked", self.take_snapshot)
		hbox.pack_end(self.button2, False, False, 0)

		# ===== Create GStreamer Receiver Pipeline ===== #
		global camv,camv_lock
		self.count = 0
		self.running = False
		self.num_snapshots = 0
		self.num_recordings = 0
		self.img_pipe = None
		self.rec_pipe = None
		self.pipeline = None
		self.launch_pipeline(pipeline)
		self.selector = self.pipeline.get_by_name('selector')
		self.selector_sink_pad_1 = self.selector.get_static_pad('sink_0')
		self.selector_sink_pad_2 = self.selector.get_static_pad('sink_1')
		self.selector_sink_pad_3 = self.selector.get_static_pad('sink_2')
		self.selector.set_property('active-pad', self.selector_sink_pad_1)
		self.active_cam="cam1"
		camv_lock.acquire()
		if camv[self.active_cam]==0: sserv_sendcmd(self.active_cam+" up")
		camv[self.active_cam]+=1
		camv_lock.release()
		self.tee = self.pipeline.get_by_name('t')
		self.tee2 = self.pipeline.get_by_name('t2')
		self.display = self.pipeline.get_by_name('display')

		# ===== Run ===== #
		self.show_all()
		self.xid = self.window.get_property('window').get_xid()
		self.play()


	def play(self):
		self.running = True
		stream = self.pipeline.set_state(Gst.State.PLAYING)
		print('Set to playing')
		if stream ==  Gst.StateChangeReturn.FAILURE:
			print('ERROR: Unable to set the pipeline to the playing state')


	def launch_pipeline(self, pipeline):
		self.pipeline = Gst.parse_launch(pipeline)
		bus = self.pipeline.get_bus()
		bus.add_signal_watch()
		bus.enable_sync_message_emission()
		bus.connect('message', self.on_message)
		bus.connect('sync-message::element', self.on_sync_message)


	def _shutdown(self):
		self.pipeline.bus.remove_signal_watch()
		self.pipeline.set_state(Gst.State.NULL)
		Gtk.main_quit()
		camv_lock.acquire()
		camv[self.active_cam]-=1
		if camv[self.active_cam]==0: sserv_sendcmd(self.active_cam+" down")
		camv_lock.release()

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


	def on_sync_message(self, bus, msg):
		struct_name = msg.get_structure().get_name()
		if struct_name == 'prepare-window-handle':
			msg.src.set_property('force-aspect-ratio', True)
			msg.src.set_window_handle(self.xid)


	def on_switch(self, button, cam):
		global camv,camv_lock
		if cam!=self.active_cam:
			if cam == 'cam1':
				self.selector.set_property('active-pad', self.selector_sink_pad_1)
			elif cam == 'cam2':
				self.selector.set_property('active-pad', self.selector_sink_pad_2)
			else:
				self.selector.set_property('active-pad', self.selector_sink_pad_3)
			camv_lock.acquire()
			if camv[cam]==0: sserv_sendcmd(cam+" up")
			camv[cam]+=1
			camv[self.active_cam]-=1
			if camv[self.active_cam]==0: sserv_sendcmd(self.active_cam+" down")
			self.active_cam=cam
			camv_lock.release()

	def record_button(self, widget):
		if self.button.get_label() == 'Start Recording':
			self.button.set_label('Stop Recording')
			self.start_recording()
		else:
			self.stop_recording()
			self.button.set_label('Start Recording')


	def start_recording(self):
		location = 'vidoutput' + str(self.num_recordings) + '.mkv'
		self.rec_pipe = Gst.parse_bin_from_description(
				"queue name=vidqueue ! "
				"h265parse ! "
				"matroskamux ! "
				"filesink name=vidsink location="+location+" async=false",
				True)
		self.pipeline.add(self.rec_pipe)
		self.tee.link(self.rec_pipe)
		self.rec_pipe.set_state(Gst.State.PLAYING)
		print('Starting Recording...')
		self.num_recordings += 1


	def stop_recording(self):
		vidqueue = self.rec_pipe.get_by_name('vidqueue')
		vidqueue.get_static_pad('src').add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, self.probe_block)
		self.tee.unlink(self.rec_pipe)
		vidqueue.get_static_pad('sink').send_event(Gst.Event.new_eos())
		print('Stopped recording')


	def probe_block(self, pad, buffer):
		print('blocked')
		return True


	def img_probe_block(self, pad, buffer):
		if self.count == 0:
			self.count += 1
			return Gst.PadProbeReturn(3)
		else:
			imgqueue = self.pipeline.get_by_name('imgqueue')
			imgqueue.get_static_pad('src').add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, self.probe_block)
			self.tee2.unlink(self.img_pipe)
			imgqueue.get_static_pad('sink').send_event(Gst.Event.new_eos())
			return Gst.PadProbeReturn(0)


	def take_snapshot(self, widget):
		location = 'imgout' + str(self.num_snapshots) + '.jpeg'
		self.img_pipe = Gst.parse_bin_from_description(
			"queue name=imgqueue ! "
			"nvvidconv ! "
			"jpegenc ! "
			"filesink name=imgsink location="+location+" async=false",
			True)
		if not self.pipeline.add(self.img_pipe):
			print('img_pipe not added to pipeline')
		if not self.tee2.link(self.img_pipe):
			print('tee was not linked with img_pipe')
		self.count = 0
		imgqueue = self.pipeline.get_by_name('imgqueue')
		self.img_pipe.set_state(Gst.State.PLAYING)
		imgqueue.get_static_pad('src').add_probe(Gst.PadProbeType.BUFFER, self.img_probe_block)
		self.num_snapshots += 1

def sserv_sendcmd(cmd):
	global srv_ip,srv_port
	sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	sock.connect((srv_ip,srv_port))
	sock.send(cmd.encode("ascii")+b'\n')
	sock.close()

def main():
	global srv_ip,srv_port
	global camv,camv_lock
	ip="192.168.2.0"#local address
	srv_ip="192.168.2.0"#sender ip
	srv_port=9990
	camv={"cam1":0,"cam2":0,"cam3":0}
	camv_lock=threading.Lock()
	GObject.threads_init()
	Gst.init(None)
	pipe = get_recv_pipeline(ip=ip)
	r = Receiver(pipe)
	Gtk.main()

def get_recv_pipeline(ip='192.168.2.0'):
	return ("udpsrc name=cam1 address="+ip+" port=8080 ! selector. "
		"udpsrc name=cam2 address="+ip+" port=8081 ! selector. "
		"udpsrc name=cam3 address="+ip+" port=8082 ! selector. "
		"input-selector name = selector ! application/x-rtp ! rtph265depay ! "
		"tee name=t ! queue ! h265parse ! omxh265dec ! "
		"tee name=t2 ! queue ! nvvidconv ! videoscale ! "
		"video/x-raw, width=640, height=480 ! ximagesink name=display")


if __name__=='__main__':
	main()
