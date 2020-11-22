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
		self.connect("destroy", Gtk.main_quit)
		self.set_resizable(False)
		self.set_default_size(1280, 480)

		# box to hold everything
		container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
		self.add(container)

		# box for each stream
		vbox_l = Gtk.VBox()
		vbox_r = Gtk.VBox()

		# area for video player
		self.area_l = Gtk.DrawingArea()
		self.area_r = Gtk.DrawingArea()
		self.area_l.set_size_request(640,480)
		self.area_r.set_size_request(640,480)
		vbox_l.pack_start(self.area_l, False, False, 0)
		vbox_r.pack_start(self.area_r, False, False, 0)
		container.pack_start(vbox_l, True, True, 0)
		container.pack_start(vbox_r, True, True, 0)

		# box to hold radio buttons for switching between streams
		self.buttonbox_l = Gtk.Box()
		vbox_l.pack_start(self.buttonbox_l, False, False, 0)

		# radio button for camera 1 - left
		self.cam1_button_l = Gtk.RadioButton.new_with_label_from_widget(None, 'Camera 1')
		self.cam1_button_l.connect('toggled', self.on_switch_l, 'cam1')
		self.buttonbox_l.add(self.cam1_button_l)

		# radio button for camera 2 - left
		self.cam2_button_l = Gtk.RadioButton.new_from_widget(self.cam1_button_l)
		self.cam2_button_l.set_label('Camera 2')
		self.cam2_button_l.connect('toggled', self.on_switch_l, 'cam2')
		self.buttonbox_l.add(self.cam2_button_l)

		# radio button for camera 3
		#self.cam3_button = Gtk.RadioButton.new_with_label_from_widget(self.cam1_button, 'Camera 3')
		#self.cam3_button.connect('toggled', self.on_switch, 'cam3')
		#self.buttonbox.add(self.cam3_button)

		# radio button for all cameras
		#self.all_button = Gtk.RadioButton.new_with_label_from_widget(self.cam1_button, 'All Cameras')
		#self.all_button.connect('toggled', self.on_switch, 'all')
		#self.buttonbox.add(self.all_button)

		# Add space for capture buttons
		hbox_l = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
		vbox_l.pack_start(hbox_l, False, False, 0)
		hbox_l.set_border_width(10)

		# Add Recording and Capture buttons
		self.button_l_r = Gtk.Button(label="Start Recording")
		self.button_l_r.connect("clicked", self.record_button_l)
		hbox_l.pack_start(self.button_l_r, False, False, 0)
		self.button_l_c = Gtk.Button(label="Take Snapshot")
		self.button_l_c.connect("clicked", self.take_snapshot)
		hbox_l.pack_end(self.button_l_c, False, False, 0)

		# Add space for capture buttons = Right
		hbox_r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
		vbox_r.pack_start(hbox_r, False, False, 0)
		hbox_r.set_border_width(10)

		# Add Recording and Capture buttons
		self.button_r_r = Gtk.Button(label="Start Recording")
		self.button_r_r.connect("clicked", self.record_button_r)
		hbox_r.pack_start(self.button_r_r, False, False, 0)
		self.button_r_c = Gtk.Button(label="Take Snapshot")
		self.button_r_c.connect("clicked", self.take_snapshot)
		hbox_r.pack_end(self.button_r_c, False, False, 0)


		# ===== Create GStreamer Receiver Pipeline ===== #
		self.count_l = 0
		self.count_r = 0
		self.num_snapshots = 0
		self.num_recordings = 0
		self.img_pipe_l = None
		self.img_pipe_r = None
		self.rec_pipe_l = None
		self.rec_pipe_r = None
		self.pipeline = None
		self.launch_pipeline(pipeline)
		self.ql = self.pipeline.get_by_name('ql')
		self.qr = self.pipeline.get_by_name('qr')
		self.t_l1 = self.pipeline.get_by_name('t_l1')
		self.t_r1 = self.pipeline.get_by_name('t_r1')
		self.t_l2 = self.pipeline.get_by_name('t_l2')
		self.t_r2 = self.pipeline.get_by_name('t_r2')
		self.display_l = self.pipeline.get_by_name('display_l')
		self.display_r = self.pipeline.get_by_name('display_r')

		# ===== Run ===== #
		self.show_all()
		self.xid_l = self.area_l.get_property('window').get_xid()
		self.xid_r = self.area_r.get_property('window').get_xid()
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
			if msg.src.get_name() == 'display_l':
				msg.src.set_window_handle(self.xid_l)
			else: msg.src.set_window_handle(self.xid_r)


	def on_switch_l(self, button, cam):
		print(cam+' button pressed')


	def record_button_l(self, widget):
		if self.button_l_r.get_label() == 'Start Recording':
			self.button_l_r.set_label('Stop Recording')
			self.start_recording('left')
		else:
			self.stop_recording('left')
			self.button_l_r.set_label('Start Recording')


	def record_button_r(self, widget):
		if self.button_r_r.get_label() == 'Start Recording':
			self.button_r_r.set_label('Stop Recording')
			self.start_recording('right')
		else:
			self.stop_recording('right')
			self.button_r_r.set_label('Start Recording')


	def start_recording(self, side):
		location = 'vidoutput' + str(self.num_recordings) + '.mkv'
		if side == 'left':
			self.rec_pipe = Gst.parse_bin_from_description(
				"queue name=vidqueue ! "
				"h265parse ! "
				"matroskamux ! "
				"filesink name=vidsink location="+location+" async=false",
				True)
			self.pipeline.add(self.rec_pipe_l)
			self.t_l1.link(self.rec_pipe)
			self.rec_pipe_l.set_state(Gst.State.PLAYING)
		else:
			self.rec_pipe = Gst.parse_bin_from_description(
				"queue name=vidqueue ! "
				"h265parse ! "
				"matroskamux ! "
				"filesink name=vidsink location="+location+" async=false",
				True)
			self.pipeline.add(self.rec_pipe_r)
			self.t_r1.link(self.rec_pipe_r)
			self.rec_pipe_r.set_state(Gst.State.PLAYING)
		print('Starting Recording...')
		self.num_recordings += 1


	def stop_recording(self, side):
		if side == 'left':
			vidqueue = self.rec_pipe_l.get_by_name('vidqueue')
		else: vidqueue = self.rec_pipe_r.get_by_name('vidqueue')
		vidqueue.get_static_pad('src').add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, self.probe_block)
		if side == 'left': self.t_l1.unlink(self.rec_pipe_l)
		else: self.t_r1.unlink(self.rec_pipe_r)
		vidqueue.get_static_pad('sink').send_event(Gst.Event.new_eos())
		print('Stopped recording')


	def probe_block(self, pad, buffer):
		print('blocked')
		return True


	### needs to be updated ###
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


	### needs to be updated ###
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


def main():
	GObject.threads_init()
	Gst.init(None)
	pipe = get_recv_pipeline()
	r = Receiver(pipe)
	Gtk.main()


def get_recv_pipeline(ip='192.168.2.0'):
	return ("udpsrc name=cam1 address="+ip+" port=8080 ! "
		"application/x-rtp ! rtph265depay ! tee name=t_l1 ! "
		"queue ! h265parse ! omxh265dec ! tee name=t_l2 ! "
		"queue ! nvvidconv ! ximagesink name=display_l "
		"udpsrc name=cam2 address="+ip+" port=8081 ! "
		"application/x-rtp ! rtph265depay ! tee name=t_r1 ! "
		"queue ! h265parse ! omxh265dec ! tee name=t_r2 ! "
		"queue ! nvvidconv ! ximagesink name=display_r")

	#return ("udpsrc name=cam1 address="+ip+" port=8080 ! selector. "
	#	"udpsrc name=cam2 address="+ip+" port=8081 ! selector. "
	#	"udpsrc name=cam3 address="+ip+" port=8082 ! selector. "
	#	"input-selector name = selector ! application/x-rtp ! rtph265depay ! "
	#	"tee name=t ! queue ! h265parse ! omxh265dec ! "
	#	"tee name=t2 ! queue ! nvvidconv ! videoscale ! "
	#	"video/x-raw, width=640, height=480 ! ximagesink name=display")


if __name__=='__main__':
	main()
