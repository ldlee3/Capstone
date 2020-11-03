# UPDATED: 10/31/2020

# File: receiver.py

# DOING: save image on demand
# DONE: save video on demand


'''
Full Receiving Pipeline:
gst-launch-1.0 udpsrc address=192.168.2.0 port=8080 ! application/x-rtp ! rtph265depay ! tee name=t !
queue ! h265parse ! omxh265dec ! nvvidconv ! ximagesink t. !
queue ! h265parse ! matroskamux ! filesink location=vidoutput#.mkv async=false t. !
queue ! h265parse ! omxh265dec ! jpegenc ! filesink location=imageout#.jpeg async=false
'''


import sys
import gi
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')
gi.require_version('GdkX11', '3.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import GObject, Gst, Gtk, GdkX11, GstVideo


ip = '192.168.2.0'
port = '8080'


def get_recv_pipeline():
	return ("udpsrc address="+ip+" port="+port+" ! application/x-rtp ! rtph265depay ! "
	"tee name=t ! queue ! h265parse ! omxh265dec ! nvvidconv ! ximagesink name=display")


class Receiver(Gtk.Window):
	def __init__(self, pipeline):
		Gtk.Window.__init__(self, title='Livestream')
		self.connect("destroy", Gtk.main_quit)
		self.set_default_size(640, 480)

		# Drawing area for Video Widget
		self.player_window = Gtk.DrawingArea()
		vbox = Gtk.VBox()
		self.add(vbox)
		vbox.add(self.player_window)

		# Add space for buttons
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

		# Create GStreamer Receiver Pipeline
		self.count = 0
		self.running = False
		self.num_snapshots = 0
		self.num_recordings = 0
		self.img_pipe = None
		self.rec_pipe = None
		self.pipeline = None
		self.launch_pipeline(pipeline)
		self.tee = self.pipeline.get_by_name('t')
		self.display = self.pipeline.get_by_name('display')

		# Run
		self.show_all()
		self.xid = self.player_window.get_property('window').get_xid()
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
		#if message.src.get_name() != 'display':
		#	print(message.src.get_name(), message.type)
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
			#self.count += 1
			return Gst.PadProbeReturn(3)
		else:
			#imgqueue = self.pipeline.get_by_name('imgqueue')
			#imgqueue.get_static_pad('src').add_probe(Gst.PadProbeType.BLOCK_UPSTREAM, self.img_probe_drop)
			return Gst.PadProbeReturn(1)


	#def img_probe_drop(self, pad, buffer):
	#	return Gst.PadProbeReturn(0)


	def take_snapshot(self, widget):
		location = 'imgout' + str(self.num_snapshots) + '.png'
		if self.num_snapshots > 0:
			self.unlink_imgpipe()
		self.img_pipe = Gst.parse_bin_from_description(
			"queue name=imgqueue ! "
			"h265parse ! "
			"omxh265dec ! "
			"nvvidconv ! "
			"pngenc ! "
			"filesink name=imgsink location="+location+" async=false",
			True)
		if not self.pipeline.add(self.img_pipe):
			print('img_pipe not added to pipeline')
		if not self.tee.link(self.img_pipe):
			print('tee was not linked with img_pipe')
		self.count = 0
		imgqueue = self.pipeline.get_by_name('imgqueue')
		self.img_pipe.set_state(Gst.State.PLAYING)
		imgqueue.get_static_pad('src').add_probe(Gst.PadProbeType.PULL, self.img_probe_block)
		self.num_snapshots += 1


	def unlink_imgpipe(self):
		imgqueue = self.img_pipe.get_by_name('imgqueue')
		imgqueue.get_static_pad('src').add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, self.probe_block)
		self.tee.unlink(self.img_pipe)
		imgqueue.get_static_pad('sink').send_event(Gst.Event.new_eos())


def main():
	GObject.threads_init()
	Gst.init(None)
	pipe = get_recv_pipeline()
	r = Receiver(pipe)
	Gtk.main()


if __name__=='__main__':
	main()
