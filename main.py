# UPDATED: 10/31/2020

# TO DO: Change from QR detection to ALVAR detection

# This program starts a Gstreamer pipeline sends it camera frames to OpenCV.
# OpenCV has the ability to process the video (currently does not) and sends the frames
# over UDP using ip 192.168.2.0 and port 8080. .


import sys
import numpy as np
import cv2
#from ar_markers import detect_markers
#from pyzbar.pyzbar import decode #for QR (and bar) code detection
import gi
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gst, Gtk
import sender


def main():
	Gst.init(None)
	cam_pipe = sender.get_pipeline('file', '')
	#cam_pipe = sender.get_pipeline('tx2', 'cam2')
	cam = sender.Sender(cam_pipe)

	out = cv2.VideoWriter(sender.get_pipeline_out(), 1, 30.0, (640,480), True)
	if not out.isOpened():
		print('videowriter not open')

	while True:
		# Wait for the next frame
		if not cam.frame_available():
			continue

		frame = cam.get_frame()
		# color correction for receiver end
		img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

		# Simple Aruco detection
		#markers = detect_markers(frame)
		#for marker in markers:
		#	marker.highlite_marker(frame)

		# for qr_code in decode(frame):
		#	myData = qr_code.data.decode('utf-8')
		#	print(myData)
		#	pts = np.array([qr_code.polygon], np.int32)
		#	pts = pts.reshape((-1,1,2))
		#	cv2.polylines(frame, [pts], True, (255, 0, 255), 5) #box around qr code
			# uncomment below 2 for decoded QR string to appear above QR Code
		#	pts2 = qr_code.rect
		#	cv2.putText(frame, myData, (pts2[0], pts2[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,0,255), 2)

		out.write(img)
		#cv2.imshow('frame', frame)

		if cv2.waitKey(1) & 0xFF == ord('q'):
			break

	cam.release()
	out.release()


if __name__ == '__main__':
	main()
