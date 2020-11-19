# UPDATED: 11/8/2020

# TO DO: Change from QR detection to ALVAR detection

# This program starts a Gstreamer pipeline sends it camera frames to OpenCV.
# OpenCV has the ability to process the video (currently does not) and sends the frames
# over UDP using ip 192.168.2.0 and port 8080.


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

	cam_pipe = sender.get_pipeline('tx2', 'cam4')
	cam_pipe2 = sender.get_pipeline('file', 'testvideo0')
	cam_pipe3 = sender.get_pipeline('tx2', 'cam3')
	cam = sender.Sender(cam_pipe)
	cam2 = sender.Sender(cam_pipe2)
	cam3 = sender.Sender(cam_pipe3)

	out = cv2.VideoWriter(sender.get_pipeline_out('192.168.2.0', '8080'), 1, 30.0, (640,480), True)
	out2 = cv2.VideoWriter(sender.get_pipeline_out('192.168.2.0', '8081'), 1, 30.0, (640,480), True)
	out3 = cv2.VideoWriter(sender.get_pipeline_out('192.168.2.0', '8082'), 1, 30.0, (640,480), True)

	if not out.isOpened():
		print('videowriter for cam1 not open')
	if not out2.isOpened():
		print('videowriter for cam2 not open')
	if not out3.isOpened():
		print('videowriter for cam3 not open')

	while True:
		# Wait for the next frame
		if not cam.frame_available():
			continue
		if not cam2.frame_available():
			continue
		if not cam3.frame_available():
			continue

		frame = cam.get_frame()
		# color correction for receiver end
		img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
		frame2 = cam2.get_frame()
		img2 = cv2.cvtColor(frame2, cv2.COLOR_RGB2BGR)
		frame3 = cam3.get_frame()
		img3 = cv2.cvtColor(frame3, cv2.COLOR_RGB2BGR)

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
		out2.write(img2)
		out3.write(img3)
		#cv2.imshow('frame', frame)

		if cv2.waitKey(1) & 0xFF == ord('q'):
			break

	cam.release()
	cam2.release()
	cam3.release()
	out.release()
	out2.release()
	out3.release()


if __name__ == '__main__':
	main()
