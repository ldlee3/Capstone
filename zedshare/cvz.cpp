/**/

#include <sys/mman.h>
#include <sys/stat.h>
#include <semaphore.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <time.h>
#include <signal.h>
#include <pthread.h>

#include "opencv2/opencv.hpp"
#include "opencv2/imgproc.hpp"
#include "opencv2/imgcodecs.hpp"
#include "opencv2/highgui.hpp"

#include "sl/Camera.hpp"

struct shm_buf{
	int shm;
	char *buf;
	char rf,wf;
	sem_t sem;
};

int flag;

void sig_h(int s){
        printf("sigint\n");
        flag=0;
}

/**
* Conversion function between sl::Mat and cv::Mat
* adapted from https://github.com/stereolabs/zed-opencv/blob/master/cpp/src/main.cpp
**/
cv::Mat slMat2cvMat(sl::Mat& input)
{
        // Mapping between MAT_TYPE and CV_TYPE
        int cv_type = -1;
        switch (input.getDataType()) {
                case sl::MAT_TYPE_32F_C1: cv_type = CV_32FC1; break;
                case sl::MAT_TYPE_32F_C2: cv_type = CV_32FC2; break;
                case sl::MAT_TYPE_32F_C3: cv_type = CV_32FC3; break;
                case sl::MAT_TYPE_32F_C4: cv_type = CV_32FC4; break;
                case sl::MAT_TYPE_8U_C1: cv_type = CV_8UC1; break;
                case sl::MAT_TYPE_8U_C2: cv_type = CV_8UC2; break;
                case sl::MAT_TYPE_8U_C3: cv_type = CV_8UC3; break;
                case sl::MAT_TYPE_8U_C4: cv_type = CV_8UC4; break;
                default: break;
        }

        // Since cv::Mat data requires a uchar* pointer, we get the uchar1 pointer from sl::Mat (getPtr<T>())
        // cv::Mat and sl::Mat will share a single memory structure
        return cv::Mat(input.getHeight(), input.getWidth(), cv_type, input.getPtr<sl::uchar1>(sl::MEM_CPU));
}

void shm_read_get(struct shm_buf *shmbuf)
{
	while(1){
		sem_wait(&(shmbuf->sem));
		if(!(shmbuf->wf)){
			shmbuf->rf++;
			sem_post(&(shmbuf->sem));
			break;
		}sem_post(&(shmbuf->sem));
	}
}

void shm_read_release(struct shm_buf *shmbuf)
{
	shmbuf->rf--;
}

void shm_load(cv::Mat img, struct shm_buf *shmbuf)//load frame from Mat
{
	sem_wait(&(shmbuf->sem));
	shmbuf->wf=1;
	sem_post(&(shmbuf->sem));
	while(shmbuf->rf);
	for(int i=0;i<img.rows;i++) memcpy(shmbuf->buf,img.ptr(i),img.cols*4);
	shmbuf->wf=0;
}

int main()
{
	size_t zed_buflen;

	sl::Camera zed;
	sl::InitParameters zed_init;
	sl::RuntimeParameters zed_run;

	signal(SIGINT,sig_h);

	zed_init.camera_resolution=sl::RESOLUTION_HD720;
	zed_init.depth_mode=sl::DEPTH_MODE_PERFORMANCE;
	zed_init.coordinate_units=sl::UNIT_MILLIMETER;

	if(zed.open(zed_init)!=sl::SUCCESS) return 1;

	zed_run.sensing_mode=sl::SENSING_MODE_STANDARD;

	sl::Resolution zed_res=zed.getResolution();
	sl::Mat left(zed_res.width,zed_res.height,sl::MAT_TYPE_8U_C4);
	sl::Mat right(zed_res.width,zed_res.height,sl::MAT_TYPE_8U_C4);
	sl::Mat depth(zed_res.width,zed_res.height,sl::MAT_TYPE_8U_C4);	
	cv::Mat cv_left=slMat2cvMat(left),cv_right=slMat2cvMat(right),cv_depth=slMat2cvMat(depth);
	cv::Mat cv_sobel(zed_res.height,zed_res.width,CV_8UC4);

	zed_buflen=zed_res.width*zed_res.height*4;
	struct shm_buf shmbuf_left,shmbuf_right,shmbuf_depth,shmbuf_sobel;
	shmbuf_left.wf=shmbuf_right.wf=shmbuf_depth.wf=shmbuf_sobel.wf=0;
	shmbuf_left.rf=shmbuf_right.rf=shmbuf_depth.rf=shmbuf_sobel.rf=0;

	if((shmbuf_left.shm=shm_open("/shm_zedleft",O_RDWR|O_CREAT|O_EXCL,S_IRUSR|S_IWUSR))==-1) return 1;
	ftruncate(shmbuf_left.shm,zed_buflen);
	shmbuf_left.buf=(char*)mmap(NULL,zed_buflen,PROT_READ|PROT_WRITE,MAP_SHARED,shmbuf_left.shm,0);
	if((shmbuf_right.shm=shm_open("/shm_zedright",O_RDWR|O_CREAT|O_EXCL,S_IRUSR|S_IWUSR))==-1) return 1;
	ftruncate(shmbuf_right.shm,zed_buflen);
	shmbuf_right.buf=(char*)mmap(NULL,zed_buflen,PROT_READ|PROT_WRITE,MAP_SHARED,shmbuf_right.shm,0);
	if((shmbuf_depth.shm=shm_open("/shm_zeddepth",O_RDWR|O_CREAT|O_EXCL,S_IRUSR|S_IWUSR))==-1) return 1;
	ftruncate(shmbuf_depth.shm,zed_buflen);
	shmbuf_depth.buf=(char*)mmap(NULL,zed_buflen,PROT_READ|PROT_WRITE,MAP_SHARED,shmbuf_depth.shm,0);
	if((shmbuf_sobel.shm=shm_open("/shm_cvsobel",O_RDWR|O_CREAT|O_EXCL,S_IRUSR|S_IWUSR))==-1) return 1;
	ftruncate(shmbuf_sobel.shm,zed_buflen);
	shmbuf_sobel.buf=(char*)mmap(NULL,zed_buflen,PROT_READ|PROT_WRITE,MAP_SHARED,shmbuf_sobel.shm,0);

	sem_init(&(shmbuf_left.sem),0,1);
	sem_init(&(shmbuf_right.sem),0,1);
	sem_init(&(shmbuf_depth.sem),0,1);
	sem_init(&(shmbuf_sobel.sem),0,1);

	//create access socket and thread
printf("init passed\n");
	flag=1;
	struct timespec framedelay;
	while(flag){
		if(zed.grab(zed_run)==sl::SUCCESS){
			zed.retrieveImage(left,sl::VIEW_LEFT);
			zed.retrieveImage(right,sl::VIEW_RIGHT);
			zed.retrieveMeasure(depth,sl::MEASURE_DEPTH);
			
			cv::Sobel(cv_left,cv_sobel,-1,1,1);
printf("frames loaded\n");
			shm_load(cv_left,&shmbuf_left);
			shm_load(cv_left,&shmbuf_right);
			shm_load(cv_left,&shmbuf_depth);
			shm_load(cv_left,&shmbuf_sobel);

			cv::imshow("Left View",cv_left);
			cv::imshow("Sobel Filter",cv_sobel);
			cv::waitKey(30);
		}framedelay.tv_sec=0;
		framedelay.tv_nsec=10000000;
		nanosleep(&framedelay,NULL);
	}
printf("loop exit\n");
	//join thread, close socket

	sem_destroy(&(shmbuf_left.sem));
	sem_destroy(&(shmbuf_right.sem));
	sem_destroy(&(shmbuf_depth.sem));
	sem_destroy(&(shmbuf_sobel.sem));

	munmap(shmbuf_left.buf,zed_buflen);
	close(shmbuf_left.shm);
	shm_unlink("/shm_zedleft");
	munmap(shmbuf_right.buf,zed_buflen);
	close(shmbuf_right.shm);
	shm_unlink("/shm_zedright");
	munmap(shmbuf_depth.buf,zed_buflen);
	close(shmbuf_depth.shm);
	shm_unlink("/shm_zeddepth");
	munmap(shmbuf_sobel.buf,zed_buflen);
	close(shmbuf_sobel.shm);
	shm_unlink("/shm_cvsobel");

	zed.close();
	return 0;
}
