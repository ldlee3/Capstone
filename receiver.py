# UPDATED: 11/28/2020
# CHANGES: There are now two displays, two sets of camera radio buttons, two sets of
#	   buttons for saving image and video in the GUI. The streams selection no longer
#	   uses input-selector but by linking/unlinking to tees. Each udpsrc is hooked up
#	   to a fakesink so that each src has a sink at all times. The queue to the fakesink
#	   is set to silent. The image saving no longer uses dynamic linking but utilizes
#	   the GUI to save the pixels from the display to a png file.

# File: receiver.py

# Contains:
#   Class
#	Receiver class - inherits from Gtk.Window, creates a Gtk Window to play the
#	incoming streams played over udp from ip 192.168.2.0 on port 8080-8082. The window
#	includes two buttons, one for capturing images and one for recording video.
#	The window also includes 3 radio buttons to switch between the 3 streams.
#	Switching between streams and recording video is done by dynamic linking/unlinking
#	as necessary. The images are captured using the Gdk by taking the image from
#	display converting it to RGB (pixbuf only compatible with RGB) and saving to file.
#   Functions
#	get_recv_pipeline() - Gst launch pipeline as a string which receives a stream
#	from a udpsrc and plays it on ximagesink display. There are two tees in the
#	pipeline for hooking in the bins for saving images and videos, and three sources
#	with an input-selector.


import sys
import gi
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')
gi.require_version('GdkX11', '3.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import GObject, Gst, Gtk, GdkX11, GstVideo, Gdk


class Receiver(Gtk.Window):
	def __init__(self, pipeline):
		# ===== Gtk GUI Setup ===== #
		Gtk.Window.__init__(self, title='Livestream')
		self.connect("destroy", Gtk.main_quit)
		self.set_resizable(False)
		self.set_default_size(960, 360)

		# box to hold everything
		container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
		self.add(container)

		# box for each stream
		vbox_l = Gtk.VBox()
		vbox_r = Gtk.VBox()

		# area for video player
		self.area_l = Gtk.DrawingArea()
		self.area_r = Gtk.DrawingArea()
		self.area_l.set_size_request(480,360)
		self.area_r.set_size_request(480,360)
		#self.area_l.connect('draw', self.on_draw)
		vbox_l.pack_start(self.area_l, False, False, 0)
		vbox_r.pack_start(self.area_r, False, False, 0)
		container.pack_start(vbox_l, True, True, 0)
		container.pack_start(vbox_r, True, True, 0)

		# box to hold radio buttons for switching between streams
		self.buttonbox_l = Gtk.Box()
		self.buttonbox_r = Gtk.Box()
		vbox_l.pack_start(self.buttonbox_l, False, False, 0)
		vbox_r.pack_start(self.buttonbox_r, False, False, 0)

		# radio button for camera 1 - left
		self.cam1_button_l = Gtk.RadioButton.new_with_label_from_widget(None, 'Camera 1')
		self.cam1_button_l.set_active(True)
		self.cam1_button_l.connect('toggled', self.on_switch_l, 'cam1')
		self.buttonbox_l.add(self.cam1_button_l)

		# radio button for camera 2 - left
		self.cam2_button_l = Gtk.RadioButton.new_with_label_from_widget(self.cam1_button_l, 'Camera 2')
		self.cam2_button_l.connect('toggled', self.on_switch_l, 'cam2')
		self.buttonbox_l.add(self.cam2_button_l)
		self.cam2_button_l.set_sensitive(False)

		# radio button for camera 3 - left
		self.cam3_button_l = Gtk.RadioButton.new_from_widget(self.cam1_button_l)
		self.cam3_button_l.set_label('Camera 3')
		self.cam3_button_l.connect('toggled', self.on_switch_l, 'cam3')
		self.buttonbox_l.add(self.cam3_button_l)

		# radio button for camera 1 - right
		self.cam1_button_r = Gtk.RadioButton.new_with_label_from_widget(None, 'Camera 1')
		self.cam1_button_r.connect('toggled', self.on_switch_r, 'cam1')
		self.buttonbox_r.add(self.cam1_button_r)
		self.cam1_button_r.set_sensitive(False)

		# radio button for camera 2 - right
		self.cam2_button_r = Gtk.RadioButton.new_with_label_from_widget(self.cam1_button_r, 'Camera 2')
		self.cam2_button_r.set_active(True)
		self.cam2_button_r.connect('toggled', self.on_switch_r, 'cam2')
		self.buttonbox_r.add(self.cam2_button_r)

		# radio button for camera 3 - right
		self.cam3_button_r = Gtk.RadioButton.new_with_label_from_widget(self.cam1_button_r, 'Camera 3')
		self.cam3_button_r.connect('toggled', self.on_switch_r, 'cam3')
		self.buttonbox_r.add(self.cam3_button_r)

		# Add space for capture buttons - left
		hbox_l = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
		vbox_l.pack_start(hbox_l, False, False, 0)
		hbox_l.set_border_width(10)

		# Add Recording and Capture buttons - left
		self.button_l_r = Gtk.Button(label="Start Recording")
		self.button_l_r.connect("clicked", self.record_button_l)
		hbox_l.pack_start(self.button_l_r, False, False, 0)
		self.button_l_c = Gtk.Button(label="Take Snapshot")
		self.button_l_c.connect("clicked", self.take_snapshot_l)
		hbox_l.pack_end(self.button_l_c, False, False, 0)

		# Add space for capture buttons - right
		hbox_r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
		vbox_r.pack_start(hbox_r, False, False, 0)
		hbox_r.set_border_width(10)

		# Add Recording and Capture buttons - right
		self.button_r_r = Gtk.Button(label="Start Recording")
		self.button_r_r.connect("clicked", self.record_button_r)
		hbox_r.pack_start(self.button_r_r, False, False, 0)
		self.button_r_c = Gtk.Button(label="Take Snapshot")
		self.button_r_c.connect("clicked", self.take_snapshot_r)
		hbox_r.pack_end(self.button_r_c, False, False, 0)

		# ===== Create GStreamer Receiver Pipeline ===== #
		self.count_l = 0
		self.count_r = 0
		self.num_snapshots = 0
		self.num_recordings = 0
		self.img_bin_l = None
		self.img_bin_r = None
		self.rec_bin_l = None
		self.rec_bin_r = None
		self.left_unlinked = False
		self.right_unlinked = False
		self.del_rec_bin_l = False
		self.del_rec_bin_r = False
		self.pipeline = None
		self.launch_pipeline(pipeline)
		self.left = 'cam1'
		self.right = 'cam2'
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
		if stream ==  Gst.StateChangeReturn.FAILURE:
			print('ERROR: Unable to set the pipeline to the playing state')
		else: print('Set to playing')


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
		if 'vidqueue' in message.src.get_name():
			struct_name = message.get_structure().get_name()
			print(message.src.get_name(), struct_name)
		if t == Gst.MessageType.ERROR:
			err, dbg = message.parse_error()
			print('ERROR:', message.src.get_name(), ':', err.message)
			print('debugging info:', dbg)
			self._shutdown()
		elif t == Gst.MessageType.EOS:
			print('EOS: ', message.src.get_name(), ':', err.message)
			print('End-Of-Stream reached')
			self._shutdown()
		else:
			pass
		return True


	def on_sync_message(self, bus, msg):
		struct_name = msg.get_structure().get_name()
		if struct_name == 'prepare-window-handle':
			msg.src.set_property('force-aspect-ratio', True)
			if msg.src.get_name() == 'display_l':
				msg.src.set_window_handle(self.xid_l)
			else: msg.src.set_window_handle(self.xid_r)


	#def on_draw(self):


	def save_image(self, cam, side):
		if side == 'left': window = self.area_l.get_window()
		else: window = self.area_r.get_window()
		pixbuf = Gdk.pixbuf_get_from_window(window, 0, 0, 480, 360)
		pixbuf.savev('image'+str(self.num_snapshots)+'_'+cam+'.png', 'png', [], [])
		print(cam+' ('+side+') captured using GUI')


	def on_switch_l(self, button, cam):
		print(cam+' button pressed')
		prev_cam_tee = self.pipeline.get_by_name(self.left)

		# unlink pipe from previous cam
		self.ql.get_static_pad('src').add_probe(Gst.PadProbeType.BLOCK, self.probe_block_switch_l)
		prev_cam_tee.unlink(self.ql)
		self.left_unlinked = True
		if self.left == 'cam1': self.cam1_button_r.set_sensitive(True)
		elif self.left == 'cam2': self.cam2_button_r.set_sensitive(True)
		elif self.left == 'cam3': self.cam3_button_r.set_sensitive(True)

		# link pipe to new cam
		new_cam_tee = self.pipeline.get_by_name(cam)
		new_cam_tee.link(self.ql)
		self.left_unlinked = False
		self.left = cam
		if cam == 'cam1': self.cam1_button_r.set_sensitive(False)
		elif cam == 'cam2': self.cam2_button_r.set_sensitive(False)
		elif cam == 'cam3': self.cam3_button_r.set_sensitive(False)


	def on_switch_r(self, button, cam):
		print(cam+' button pressed')
		prev_cam_tee = self.pipeline.get_by_name(self.right)

		# unlink pipe from previous cam
		self.qr.get_static_pad('src').add_probe(Gst.PadProbeType.BLOCK, self.probe_block_switch_r)
		prev_cam_tee.unlink(self.qr)
		self.right_unlinked = True
		if self.right == 'cam1': self.cam1_button_l.set_sensitive(True)
		elif self.right == 'cam2': self.cam2_button_l.set_sensitive(True)
		elif self.right == 'cam3': self.cam3_button_l.set_sensitive(True)

		# link pipe to new cam
		new_cam_tee = self.pipeline.get_by_name(cam)
		new_cam_tee.link(self.qr)
		self.right_unlinked = False
		self.right = cam
		if cam == 'cam1': self.cam1_button_l.set_sensitive(False)
		elif cam == 'cam2': self.cam2_button_l.set_sensitive(False)
		elif cam == 'cam3': self.cam3_button_l.set_sensitive(False)


	def probe_block_switch_l(self, pad, info):
		if self.left_unlinked:
			return Gst.PadProbeReturn.REMOVE
		else:
			return Gst.PadProbeReturn.DROP


	def probe_block_switch_r(self, pad, info):
		if self.right_unlinked:
			return Gst.PadProbeReturn.REMOVE
		else:
			return Gst.PadProbeReturn.DROP


	def del_bin(self, side):
		if side == 'left':
			if self.del_rec_bin_l:
				print('deleting left vidbin')
				self.rec_bin_l.set_state(Gst.State.NULL)
				del self.rec_bin_l
				self.rec_bin_l = None
		else:
			if self.del_rec_bin_r:
				print('deleting right vidbin')
				self.rec_bin_r.set_state(Gst.State.NULL)
				del self.rec_bin_r
				self.rec_bin_r = None


	def record_button_l(self, widget):
		if self.button_l_r.get_label() == 'Start Recording':
			self.button_l_r.set_label('Stop Recording')
			self.start_recording_l('vidqueue_l', self.left)
		else:
			self.stop_recording_l()
			self.button_l_r.set_label('Start Recording')


	def record_button_r(self, widget):
		if self.button_r_r.get_label() == 'Start Recording':
			self.button_r_r.set_label('Stop Recording')
			self.start_recording_r('vidqueue_r', self.right)
		else:
			self.stop_recording_r()
			self.button_r_r.set_label('Start Recording')


	def start_recording_l(self, queue_name, cam):
		self.del_bin('left')
		location = 'video'+str(self.num_recordings)+'_'+cam+'.mkv'
		self.rec_bin_l = Gst.parse_bin_from_description(
			"queue name="+queue_name+" flush-on-eos=true ! "
			"h265parse ! "
			"matroskamux ! "
			"filesink location="+location+" async=false ",
			True)
		if not self.pipeline.add(self.rec_bin_l):
			print('left record pipe could not be added')
		if not self.t_l1.link(self.rec_bin_l):
			print('left record pipe could not be linked with tee')
		self.rec_bin_l.set_state(Gst.State.PLAYING)
		vidqueue = self.pipeline.get_by_name(queue_name)
		vidqueue.get_static_pad('src').add_probe(Gst.PadProbeType.BUFFER, self.vid_probe_buff)
		print('Starting Recording on ' + cam + '...')
		self.num_recordings += 1


	def vid_probe_buff(self, pad, buffer):
		return Gst.PadProbeReturn.PASS


	def start_recording_r(self, queue_name, cam):
		self.del_bin('right')
		location = 'video'+str(self.num_recordings)+'_'+cam+'.mkv'
		recbin = ("queue name="+queue_name+" flush-on-eos=true ! "
			"h265parse ! "
			"matroskamux ! "
			"filesink location="+location+" async=false ")
		self.rec_bin_r = Gst.parse_bin_from_description(recbin, True)
		if not self.pipeline.add(self.rec_bin_r):
			print('right record pipe could not be added')
		if not self.t_r1.link(self.rec_bin_r):
			print('right record pipe could not be linked')
		self.rec_bin_r.set_state(Gst.State.PLAYING)
		print('Starting Recording on ' + cam + '...')
		self.num_recordings += 1


	def stop_recording_l(self):
		vidqueue = self.rec_bin_l.get_by_name('vidqueue_l')
		vidqueue.get_static_pad('src').add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, self.probe_block_rec_l)
		print('Stopped recording')


	def stop_recording_r(self):
		vidqueue = self.rec_bin_r.get_by_name('vidqueue_r')
		vidqueue.get_static_pad('src').add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, self.probe_block)
		if not self.t_r1.unlink(self.rec_bin_r):
			print('right recording pipe could not be unlinked')
		vidqueue.get_static_pad('sink').send_event(Gst.Event.new_eos())
		self.del_rec_bin_r = True
		print('Stopped recording')


	def probe_block_rec_l(self, pad, buffer):
		print('left rec blocked')
		if not self.t_l1.unlink(self.rec_bin_l):
			print('left recording pipe could not be unlinked')
		vidqueue = self.rec_bin_l.get_by_name('vidqueue_l')
		vidqueue.get_static_pad('sink').send_event(Gst.Event.new_eos())
		self.del_rec_bin_l = True
		return Gst.PadProbeReturn.DROP


	def probe_block(self, pad, buffer):
		print('blocked')
		return Gst.PadProbeReturn.DROP


	def take_snapshot_l(self, widget):
		self.save_image(self.left, 'left')
		#location = 'image' + str(self.num_snapshots) + '_' + self.left + '.jpeg'
		#self.img_bin_l = Gst.parse_bin_from_description(
		#	"queue name=imgqueue_l ! "
		#	"nvvidconv ! "
 		#	"jpegenc ! "
		#	"filesink location="+location+" async=false",
		#	True)
		#if not self.pipeline.add(self.img_bin_l):
		#	print('left img_bin not added to pipeline')
		#if not self.t_l2.link(self.img_bin_l):
		#	print('tee was notlinked with left img_bin')
		#self.count_l = 0
		#imgqueue = self.pipeline.get_by_name('imgqueue_l')
		#self.img_bin_l.set_state(Gst.State.PLAYING)
		#imgqueue.get_static_pad('src').add_probe(Gst.PadProbeType.BUFFER, self.img_probe_block_l)
		self.num_snapshots += 1


	def take_snapshot_r(self, widget):
		self.save_image(self.right, 'right')
		#location = 'image' + str(self.num_snapshots) + '_' + self.right + '.jpeg'
		#self.img_bin_r = Gst.parse_bin_from_description(
		#	"queue name=imgqueue_r ! "
		#	"nvvidconv ! "
		#	"jpegenc ! "
		#	"filesink location="+location+" async=false",
		#	True)
		#if not self.pipeline.add(self.img_bin_r):
		#	print('right img_bin not added to pipeline')
		#if not self.t_r2.link(self.img_bin_r):
		#	print('right tee was not linked with img_bin')
		#self.count_r = 0
		#imgqueue = self.pipeline.get_by_name('imgqueue_r')
		#self.img_bin_r.set_state(Gst.State.PLAYING)
		#imgqueue.get_static_pad('src').add_probe(Gst.PadProbeType.BUFFER, self.img_probe_block_r)
		self.num_snapshots += 1


	#def img_probe_block_l(self, pad, buffer):
	#	if self.count_l == 0:
	#		self.count_l += 1
	#		return Gst.PadProbeReturn.PASS
	#	else:
	#		imgqueue = self.pipeline.get_by_name('imgqueue_l')
	#		imgqueue.get_static_pad('src').add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, self.probe_block)
	#		self.t_l2.unlink(self.img_bin_l)
	#		imgqueue.get_static_pad('sink').send_event(Gst.Event.new_eos())
	#		print('Captured: Left')
	#		#return Gst.PadProbeReturn.DROP
	#		return Gst.PadProbeReturn.REMOVE


	#def img_probe_block_r(self, pad, buffer):
	#	if self.count_r == 0:
	#		self.count_r += 1
	#		return Gst.PadProbeReturn.PASS
	#	else:
	#		imgqueue = self.pipeline.get_by_name('imgqueue_r')
	#		imgqueue.get_static_pad('src').add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, self.probe_block)
	#		self.t_r2.unlink(self.img_bin_r)
	#		imgqueue.get_static_pad('sink').send_event(Gst.Event.new_eos())
	#		print('Captured: Right')
	#		return Gst.PadProbeReturn.REMOVE


def main():
	GObject.threads_init()
	Gst.init(None)
	pipe = get_recv_pipeline()
	r = Receiver(pipe)
	Gtk.main()


def get_recv_pipeline(ip='192.168.2.0'):
	return ("udpsrc address="+ip+" port=8080 ! tee name=cam1 ! "
		"queue name=ql ! application/x-rtp ! rtph265depay ! "
		"tee name=t_l1 ! queue ! h265parse ! omxh265dec ! "
		"tee name=t_l2 ! queue ! nvvidconv ! ximagesink name=display_l "
		"cam1. ! queue silent=true ! fakesink async=false "

		"udpsrc address="+ip+" port=8081 ! tee name=cam2 ! "
		"queue name=qr ! application/x-rtp ! rtph265depay ! "
		"tee name=t_r1 ! queue ! h265parse ! omxh265dec ! "
		"tee name=t_r2 ! queue ! nvvidconv ! ximagesink name=display_r "
		"cam2. ! queue silent=true ! fakesink async=false "

		"udpsrc address="+ip+" port=8082 ! tee name=cam3 ! "
		"queue silent=true ! fakesink async=false ")


if __name__=='__main__':
	main()
