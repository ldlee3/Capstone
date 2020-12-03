/**/

#include <sys/mman.h>
#include <sys/stat.h>
#include <semaphore.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <time.h>
#include <string.h>
#include <signal.h>
#include <pthread.h>

#include "opencv2/opencv.hpp"
#include "opencv2/imgproc.hpp"
#include "opencv2/imgcodecs.hpp"
#include "opencv2/highgui.hpp"

#include "sl/Camera.hpp"

#include "shmbuf.h"
#include "upc.h"

int flag;

pthread_mutex_t mtx_buf;
int fl_left,fl_right,fl_depth,fl_sobel;
struct shmbuf shmbuf_left,shmbuf_right,shmbuf_depth,shmbuf_sobel;

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

void upcmsg_h(const char *msg)
{
	printf("UPC server error: %s\n",msg);
	flag=0;
}

char *upccmd_h(const char *cmd)
{
	char *reply;
	
	if((reply=(char*)malloc(64))==NULL) return NULL;;
	
	if(!strcmp(cmd,"set left up")){
		pthread_mutex_lock(&mtx_buf);
		fl_left=1;
		pthread_mutex_unlock(&mtx_buf);
		strcpy(reply,"ACK");
	}else if(!strcmp(cmd,"set right up")){
		pthread_mutex_lock(&mtx_buf);
		fl_right=1;
		pthread_mutex_unlock(&mtx_buf);
		strcpy(reply,"ACK");
	}else if(!strcmp(cmd,"set depth up")){
		pthread_mutex_lock(&mtx_buf);
		fl_depth=1;
		pthread_mutex_unlock(&mtx_buf);
		strcpy(reply,"ACK");
	}else if(!strcmp(cmd,"set sobel up")){
		pthread_mutex_lock(&mtx_buf);
		fl_sobel=1;
		pthread_mutex_unlock(&mtx_buf);
		strcpy(reply,"ACK");
	}else if(!strcmp(cmd,"set left down")){
		pthread_mutex_lock(&mtx_buf);
		fl_left=0;
		pthread_mutex_unlock(&mtx_buf);
		strcpy(reply,"ACK");
	}else if(!strcmp(cmd,"set right down")){
		pthread_mutex_lock(&mtx_buf);
		fl_right=0;
		pthread_mutex_unlock(&mtx_buf);
		strcpy(reply,"ACK");
	}else if(!strcmp(cmd,"set depth down")){
		pthread_mutex_lock(&mtx_buf);
		fl_depth=0;
		pthread_mutex_unlock(&mtx_buf);
		strcpy(reply,"ACK");
	}else if(!strcmp(cmd,"set sobel down")){
		pthread_mutex_lock(&mtx_buf);
		fl_sobel=0;
		pthread_mutex_unlock(&mtx_buf);
		strcpy(reply,"ACK");
	}else if(!strcmp(cmd,"get left status")){
		pthread_mutex_lock(&mtx_buf);
		if(fl_left) strcpy(reply,"UP");
		else strcpy(reply,"DOWN");
		pthread_mutex_unlock(&mtx_buf);
	}else if(!strcmp(cmd,"get right status")){
		pthread_mutex_lock(&mtx_buf);
		if(fl_right) strcpy(reply,"UP");
		else strcpy(reply,"DOWN");
		pthread_mutex_unlock(&mtx_buf);
	}else if(!strcmp(cmd,"get depth status")){
		pthread_mutex_lock(&mtx_buf);
		if(fl_depth) strcpy(reply,"UP");
		else strcpy(reply,"DOWN");
		pthread_mutex_unlock(&mtx_buf);
	}else if(!strcmp(cmd,"get sobel status")){
		pthread_mutex_lock(&mtx_buf);
		if(fl_sobel) strcpy(reply,"UP");
		else strcpy(reply,"DOWN");
		pthread_mutex_unlock(&mtx_buf);
	}else if(!strcmp(cmd,"read left lock")){
		pthread_mutex_lock(&mtx_buf);
		if(fl_left){
			pthread_mutex_unlock(&mtx_buf);
			shmbuf_read_lock(&shmbuf_left);
			snprintf(reply,64,"ACK %d",shmbuf_left.frame);
		}else{
			pthread_mutex_unlock(&mtx_buf);
			strcpy(reply,"DOWN");
		}
	}else if(!strcmp(cmd,"read right lock")){
		pthread_mutex_lock(&mtx_buf);
		if(fl_right){
			pthread_mutex_unlock(&mtx_buf);
			shmbuf_read_lock(&shmbuf_right);
			snprintf(reply,64,"ACK %d",shmbuf_right.frame);
		}else{
			pthread_mutex_unlock(&mtx_buf);
			strcpy(reply,"DOWN");
		}
	}else if(!strcmp(cmd,"read depth lock")){
		pthread_mutex_lock(&mtx_buf);
		if(fl_depth){
			pthread_mutex_unlock(&mtx_buf);
			shmbuf_read_lock(&shmbuf_depth);
			snprintf(reply,64,"ACK %d",shmbuf_depth.frame);
		}else{
 			pthread_mutex_unlock(&mtx_buf);
			strcpy(reply,"DOWN");
		}
	}else if(!strcmp(cmd,"read sobel lock")){
		pthread_mutex_lock(&mtx_buf);
		if(fl_sobel){
			pthread_mutex_unlock(&mtx_buf);
			shmbuf_read_lock(&shmbuf_sobel);
			snprintf(reply,64,"ACK %d",shmbuf_sobel.frame);
		}else{
			pthread_mutex_unlock(&mtx_buf);
			strcpy(reply,"DOWN");
		}
	}else if(!strcmp(cmd,"read left release")){
		shmbuf_read_release(&shmbuf_left);
		strcpy(reply,"ACK");
	}else if(!strcmp(cmd,"read right release")){
		shmbuf_read_release(&shmbuf_right);
		strcpy(reply,"ACK");
	}else if(!strcmp(cmd,"read depth release")){
		shmbuf_read_release(&shmbuf_depth);
		strcpy(reply,"ACK");
	}else if(!strcmp(cmd,"read sobel release")){
		shmbuf_read_release(&shmbuf_sobel);
		strcpy(reply,"ACK");
	}else strcpy(reply,"UNKNOWN");	
	
	return reply;
}

int main()
{
	size_t zed_buflen;
	struct upc_inst *upc;

	sl::Camera zed;
	sl::InitParameters zed_init;
	sl::RuntimeParameters zed_run;

	signal(SIGINT,sig_h);

	zed_init.camera_resolution=sl::RESOLUTION_HD720;
	zed_init.depth_mode=sl::DEPTH_MODE_PERFORMANCE;
	zed_init.coordinate_units=sl::UNIT_MILLIMETER;
	if(zed.open(zed_init)!=sl::SUCCESS){
		printf("zed init failure\n");
		return 1;
	}zed_run.sensing_mode=sl::SENSING_MODE_STANDARD;

	sl::Resolution zed_res=zed.getResolution();
	zed_buflen=zed_res.width*zed_res.height*4;
	printf("resolution %ldx%ld\n",zed_res.width,zed_res.height);
	
	if(pthread_mutex_init(&mtx_buf,NULL)!=0) return -1;

	if(shmbuf_init(&shmbuf_left,"shm_zedleft",zed_buflen)==-1){
		printf("shared memory buffer init failure left\n");
		pthread_mutex_destroy(&mtx_buf);
		zed.close();
		return -1;
	}if(shmbuf_init(&shmbuf_right,"shm_zedright",zed_buflen)==-1){
		printf("shared memory buffer init failure right\n");
		shmbuf_destroy(&shmbuf_left);
		pthread_mutex_destroy(&mtx_buf);
		zed.close();
		return -1;
	}if(shmbuf_init(&shmbuf_depth,"shm_zeddepth",zed_buflen)==-1){
		printf("shared memory buffer init failure depth\n");
		shmbuf_destroy(&shmbuf_left);
		shmbuf_destroy(&shmbuf_right);
		pthread_mutex_destroy(&mtx_buf);
		zed.close();
		return -1;
	}if(shmbuf_init(&shmbuf_sobel,"shm_cvsobel",zed_buflen)==-1){
		printf("shared memory buffer init failure sobel\n");
		shmbuf_destroy(&shmbuf_left);
		shmbuf_destroy(&shmbuf_right);
		shmbuf_destroy(&shmbuf_depth);
		pthread_mutex_destroy(&mtx_buf);
		zed.close();
		return -1;
	}

	sl::Mat left(zed_res.width,zed_res.height,sl::MAT_TYPE_8U_C4,shmbuf_left.buf,zed_res.width*4,sl::MEM_CPU);
	sl::Mat right(zed_res.width,zed_res.height,sl::MAT_TYPE_8U_C4,shmbuf_right.buf,zed_res.width*4,sl::MEM_CPU);
	sl::Mat depth(zed_res.width,zed_res.height,sl::MAT_TYPE_8U_C4,shmbuf_depth.buf,zed_res.width*4,sl::MEM_CPU);
	cv::Mat cv_left=slMat2cvMat(left),cv_right=slMat2cvMat(right),cv_depth=slMat2cvMat(depth);
	cv::Mat cv_sobel(zed_res.height,zed_res.width,CV_8UC4,shmbuf_sobel.buf);

	if((upc=upc_init("/home/nvidia/roverupc/","cvzshare",&upccmd_h,&upcmsg_h,-1,5))==NULL){
		printf("upc init failure\n");
		shmbuf_destroy(&shmbuf_left);
		shmbuf_destroy(&shmbuf_right);
		shmbuf_destroy(&shmbuf_depth);
		shmbuf_destroy(&shmbuf_sobel);
		pthread_mutex_destroy(&mtx_buf);
		zed.close();
		return -1;
	}
	
printf("init passed\n");
	flag=fl_right=fl_left=fl_depth=fl_sobel=1;
	struct timespec framedelay;
	while(flag){
		if(zed.grab(zed_run)==sl::SUCCESS){
			pthread_mutex_lock(&mtx_buf);
			if(fl_left){
				shmbuf_write_lock(&shmbuf_left);
				zed.retrieveImage(left,sl::VIEW_LEFT);
				//memcpy(shmbuf_left.buf,cv_left.data,shmbuf_left.bufsz);
				shmbuf_left.frame=(shmbuf_left.frame+1)%32;
				shmbuf_write_release(&shmbuf_left);
			}if(fl_right){
				shmbuf_write_lock(&shmbuf_right);
				zed.retrieveImage(right,sl::VIEW_RIGHT);
				//memcpy(shmbuf_right.buf,cv_right.data,shmbuf_right.bufsz);
				shmbuf_right.frame=(shmbuf_right.frame+1)%32;
				shmbuf_write_release(&shmbuf_right);
			}if(fl_depth){
				shmbuf_write_lock(&shmbuf_depth);
				zed.retrieveImage(depth,sl::VIEW_DEPTH);
				//memcpy(shmbuf_depth.buf,cv_depth.data,shmbuf_depth.bufsz);
				shmbuf_depth.frame=(shmbuf_depth.frame+1)%32;
				shmbuf_write_release(&shmbuf_depth);
			}if(fl_sobel){
				shmbuf_write_lock(&shmbuf_sobel);
				//cv::Sobel(cv_left,cv_sobel,-1,1,1);
				cv::threshold(cv_left,cv_sobel,40,255,cv::THRESH_BINARY);
				//memcpy(shmbuf_sobel.buf,cv_sobel.data,shmbuf_sobel.bufsz);
				shmbuf_sobel.frame=(shmbuf_sobel.frame+1)%32;
				shmbuf_write_release(&shmbuf_sobel);
			}pthread_mutex_unlock(&mtx_buf);
//printf("shared buffers loaded\n");

			//cv::imshow("Left View",cv_depth);
			//cv::imshow("Sobel Filter",cv_sobel);
			//cv::waitKey(30);
		}else{
			printf("ZED grab fail\n");
			break;
		}framedelay.tv_sec=0;
		framedelay.tv_nsec=15000000;
		nanosleep(&framedelay,NULL);
	}
printf("loop exit\n");

	upc_stop(upc);	

	shmbuf_destroy(&shmbuf_sobel);
	shmbuf_destroy(&shmbuf_depth);
	shmbuf_destroy(&shmbuf_right);
	shmbuf_destroy(&shmbuf_left);

	pthread_mutex_destroy(&mtx_buf);

	zed.close();
	return 0;
}
