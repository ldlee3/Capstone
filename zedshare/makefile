

CC=g++
CFLAGS=-O3 -std=c++0x -Wall
LFLAGS=-Wl,-rpath,/usr/local/cuda/lib64:/usr/local/zed/lib:/usr/local/lib
INCL=-I/usr/local/cuda/include -I/usr/local/zed/include -I/usr/local/include/opencv -isystem /usr/local/include
SLIB=-L/usr/local/cuda/lib64 -L/usr/local/zed/lib -L/usr/local/lib
DLIB=/usr/local/zed/lib/libsl_input.so /usr/local/zed/lib/libsl_core.so /usr/local/zed/lib/libsl_zed.so -lpthread -lrt /usr/local/cuda/lib64/libcudart.so /usr/local/cuda/lib64/libnpps.so /usr/local/lib/libopencv_ml.so.3.4.3 /usr/local/lib/libopencv_cudaobjdetect.so.3.4.3 /usr/local/lib/libopencv_shape.so.3.4.3 /usr/local/lib/libopencv_superres.so.3.4.3 /usr/local/lib/libopencv_stitching.so.3.4.3 /usr/local/lib/libopencv_cudafeatures2d.so.3.4.3 /usr/local/lib/libopencv_dnn.so.3.4.3 /usr/local/lib/libopencv_videostab.so.3.4.3 /usr/local/lib/libopencv_cudabgsegm.so.3.4.3 /usr/local/lib/libopencv_cudastereo.so.3.4.3 /usr/local/lib/libopencv_cudacodec.so.3.4.3 /usr/local/lib/libopencv_photo.so.3.4.3 /usr/local/lib/libopencv_cudaoptflow.so.3.4.3 /usr/local/lib/libopencv_cudalegacy.so.3.4.3 /usr/local/lib/libopencv_objdetect.so.3.4.3 /usr/local/lib/libopencv_cudaimgproc.so.3.4.3 /usr/local/lib/libopencv_cudawarping.so.3.4.3 /usr/local/lib/libopencv_cudafilters.so.3.4.3 /usr/local/lib/libopencv_cudaarithm.so.3.4.3 /usr/local/lib/libopencv_video.so.3.4.3 /usr/local/lib/libopencv_calib3d.so.3.4.3 /usr/local/lib/libopencv_features2d.so.3.4.3 /usr/local/lib/libopencv_flann.so.3.4.3 /usr/local/lib/libopencv_highgui.so.3.4.3 /usr/local/lib/libopencv_videoio.so.3.4.3 /usr/local/lib/libopencv_imgcodecs.so.3.4.3 /usr/local/lib/libopencv_imgproc.so.3.4.3 /usr/local/lib/libopencv_core.so.3.4.3 /usr/local/lib/libopencv_cudev.so.3.4.3

upc.o: upc.c upc.h
	$(CC) $(CFLAGS) -o upc.o -c upc.c

shmbuf.o: shmbuf.c shmbuf.h
	$(CC) $(CFLAGS) -o shmbuf.o -c shmbuf.c

cvz.o: cvz.cpp upc.h shmbuf.h
	$(CC) $(INCL) $(CFLAGS) -o cvz.o -c cvz.cpp

cvzview.o: cvzview.cpp upc.h
	$(CC) $(INCL) $(CFLAGS) -o cvzview.o -c cvzview.cpp

CVZView: cvzview.o upc.o
	$(CC) -o CVZView cvzview.o upc.o $(SLIB) -rdynamic $(DLIB) $(LFLAGS)

CVZShare: cvz.o upc.o shmbuf.o
	$(CC) -o CVZShare cvz.o upc.o shmbuf.o $(SLIB) -rdynamic $(DLIB) $(LFLAGS)

clean:
	rm CVZShare cvz.o upc.o shmbuf.o CVZView cvzview.o

crashclean: CVZView
	unlink /home/nvidia/roverupc/comm/cvzshare.sock
	./CVZView
