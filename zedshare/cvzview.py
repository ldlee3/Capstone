import os
import sys
import mmap
import socket
import posix_ipc

import numpy as np
import cv2

buf_w=1280
buf_h=720
buf_d=4
buf_sz=buf_w*buf_h*buf_d

upcroot="/home/nvidia/roverupc/"

shm_l=posix_ipc.SharedMemory("shm_zedleft",read_only=True)
memm_l=mmap.mmap(shm_l.fd,buf_sz,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ)
csock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)

csock.connect(upcroot+"comm/cvzshare.sock")

csock.send(b"set left up\0")
reply=csock.recv(64)
print(reply)

while True:
	try:
		csock.send(b"read left lock\0")
		reply=csock.recv(64)
		print(reply)
		
		dat=memm_l.read(buf_sz)
		memm_l.seek(0)
	finally:
		csock.send(b"read left release\0")
		reply=csock.recv(64)
		print(reply)
	try:
		npdat=np.frombuffer(dat,dtype=np.ubyte)
		dat1=npdat.reshape(buf_h,buf_w,buf_d)
		
		cv2.imshow("left img",dat1)
		if cv2.waitKey(30)==27: raise Exception()
	except:
		cv2.destroyAllWindows()
		break

csock.send(b"set left down")
csock.close()
memm_l.close()
shm_l.close_fd()
