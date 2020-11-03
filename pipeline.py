# File: pipeline.py

# Contains: GstPipeline class - base class for our Gstreamer pipelines
#           The GstPipeline class handles initializing a new pipeline,
#           setting it to play, getting a bus and shutting down the pipeline.


import sys
import gi
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GLib, GObject


class GstPipeline:
	def __init__(self, pipeline):
		self.frame = None
		self.running = False
		self.pipeline = None


	def play(self):
		self.running = True
		stream = self.pipeline.set_state(Gst.State.PLAYING)
		print('Set to playing')
		if stream ==  Gst.StateChangeReturn.FAILURE:
			print('ERROR: Unable to set the pipeline to the playing state')


	def launch_pipeline(self, pipeline)
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
		#else:
		#	print('ERROR: Unexpected message received')
		return True


	def _shutdown(self):
		self.pipeline.bus.remove_signal_watch()
		self.pipeline.set_state(Gst.State.NULL)
