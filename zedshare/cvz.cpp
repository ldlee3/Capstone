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

#include "upc.h"

struct shm_buf{
	char *name;
	int shm,frame;
	size_t buflen;
	char *buf;
	char rf,wf;
	sem_t sem;
};

int flag;

pthread_mutex_t mtx_buf;
int fl_left,fl_right,fl_depth,fl_sobel;
struct shm_buf shmbuf_left,shmbuf_right,shmbuf_depth,shmbuf_sobel;

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

int shmbuf_read_get(struct shm_buf *shmbuf)
{
	while(1){
		sem_wait(&(shmbuf->sem));
		if(!(shmbuf->wf)){
			shmbuf->rf++;
			sem_post(&(shmbuf->sem));
			break;
		}sem_post(&(shmbuf->sem));
	}return shmbuf->frame;
}

void shmbuf_read_release(struct shm_buf *shmbuf)
{
	sem_wait(&(shmbuf->sem));
	if(shmbuf->rf>0) shmbuf->rf--;
	sem_post(&(shmbuf->sem));
}

void shmbuf_load(cv::Mat img, struct shm_buf *shmbuf)//load frame from Mat
{
	sem_wait(&(shmbuf->sem));
	shmbuf->wf=1;
	sem_post(&(shmbuf->sem));
	while(shmbuf->rf);
	for(int i=0;i<img.rows;i++) memcpy(shmbuf->buf,img.ptr(i),img.cols*4);
	shmbuf->frame=(shmbuf->frame+1)%32;
	shmbuf->wf=0;
}

void shmbuf_destroy(struct shm_buf *shmbuf){
	sem_destroy(&(shmbuf->sem));
	munmap(shmbuf->buf,shmbuf->buflen);
	close(shmbuf->shm);
	shm_unlink(shmbuf->name);
	free(shmbuf->name);
}

int shmbuf_init(struct shm_buf *shmbuf, const char *shmname, size_t buflen)
{
	shmbuf->wf=0;
	shmbuf->rf=0;
	shmbuf->frame=0;
	shmbuf->buflen=buflen;
	if((shmbuf->name=(char*)malloc(strlen(shmname)+2))==NULL) return -1;
	shmbuf->name[0]='/';
	strcpy(shmbuf->name+1,shmname);
	
	if((shmbuf->shm=shm_open(shmbuf->name,O_RDWR|O_CREAT|O_EXCL,S_IRUSR|S_IWUSR))==-1){
		free(shmbuf->name);
		return -1;
	}if(ftruncate(shmbuf->shm,shmbuf->buflen)==-1){
		close(shmbuf->shm);
		shm_unlink(shmbuf->name);
		free(shmbuf->name);
		return -1;
	}if((shmbuf->buf=(char*)mmap(NULL,shmbuf->buflen,PROT_READ|PROT_WRITE,MAP_SHARED,shmbuf->shm,0))==MAP_FAILED){
		close(shmbuf->shm);
		shm_unlink(shmbuf->name);
		free(shmbuf->name);
		return -1;
	}if((sem_init(&(shmbuf->sem),0,1))==-1){
		munmap(shmbuf->buf,shmbuf->buflen);
		close(shmbuf->shm);
		shm_unlink(shmbuf->name);
		free(shmbuf->name);
		return -1;
	}
	
	return 0;
}

void upcmsg_h(const char *msg)
{
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
			int tmp=shmbuf_read_get(&shmbuf_left);
			snprintf(reply,64,"ACK %d",tmp);
		}else strcpy(reply,"DOWN");
		pthread_mutex_unlock(&mtx_buf);
	}else if(!strcmp(cmd,"read right lock")){
		pthread_mutex_lock(&mtx_buf);
		if(fl_right){
			int tmp=shmbuf_read_get(&shmbuf_right);
			snprintf(reply,64,"ACK %d",tmp);
		}else strcpy(reply,"DOWN");
		pthread_mutex_unlock(&mtx_buf);
	}else if(!strcmp(cmd,"read depth lock")){
		pthread_mutex_lock(&mtx_buf);
		if(fl_depth){
			int tmp=shmbuf_read_get(&shmbuf_depth);
			snprintf(reply,64,"ACK %d",tmp);
		}else strcpy(reply,"DOWN");
		pthread_mutex_unlock(&mtx_buf);
	}else if(!strcmp(cmd,"read sobel lock")){
		pthread_mutex_lock(&mtx_buf);
		if(fl_sobel){
			int tmp=shmbuf_read_get(&shmbuf_sobel);
			snprintf(reply,64,"ACK %d",tmp);
		}else strcpy(reply,"DOWN");
		pthread_mutex_unlock(&mtx_buf);
	}else if(!strcmp(cmd,"read left release")){
		shmbuf_read_release(&shmbuf_left);
		strcpy(reply,"ACK");
	}else if(!strcmp(cmd,"read right release")){
		shmbuf_read_release(&shmbuf_right);
		strcpy(reply,"ACK");
	}else if(!strcmp(cmd,"read depth release")){
		shmbuf_read_release(&shmbuf_depth);
		strcpy(reply,"ACK");
	}else if(!strcmp(cmd,"read soble release")){
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

	if(zed.open(zed_init)!=sl::SUCCESS) return 1;

	zed_run.sensing_mode=sl::SENSING_MODE_STANDARD;

	sl::Resolution zed_res=zed.getResolution();
	sl::Mat left(zed_res.width,zed_res.height,sl::MAT_TYPE_8U_C4);
	sl::Mat right(zed_res.width,zed_res.height,sl::MAT_TYPE_8U_C4);
	sl::Mat depth(zed_res.width,zed_res.height,sl::MAT_TYPE_8U_C4);	
	cv::Mat cv_left=slMat2cvMat(left),cv_right=slMat2cvMat(right),cv_depth=slMat2cvMat(depth);
	cv::Mat cv_sobel(zed_res.height,zed_res.width,CV_8UC4);

	zed_buflen=zed_res.width*zed_res.height*4;
	
	if(pthread_mutex_init(&mtx_buf,NULL)!=0) return -1;

	if(shmbuf_init(&shmbuf_left,"shm_zedleft",zed_buflen)==-1){
		pthread_mutex_destroy(&mtx_buf);
		zed.close();
		return -1;
	}if(shmbuf_init(&shmbuf_right,"shm_zedright",zed_buflen)==-1){
		shmbuf_destroy(&shmbuf_left);
		pthread_mutex_destroy(&mtx_buf);
		zed.close();
		return -1;
	}if(shmbuf_init(&shmbuf_depth,"shm_zeddepth",zed_buflen)==-1){
		shmbuf_destroy(&shmbuf_left);
		shmbuf_destroy(&shmbuf_right);
		pthread_mutex_destroy(&mtx_buf);
		zed.close();
		return -1;
	}if(shmbuf_init(&shmbuf_sobel,"shm_cvsobel",zed_buflen)==-1){
		shmbuf_destroy(&shmbuf_left);
		shmbuf_destroy(&shmbuf_right);
		shmbuf_destroy(&shmbuf_depth);
		pthread_mutex_destroy(&mtx_buf);
		zed.close();
		return -1;
	}

	if((upc=upc_init("~/roverupc/","cvzshare",&upccmd_h,&upcmsg_h,-1,2))==NULL){
		shmbuf_destroy(&shmbuf_left);
		shmbuf_destroy(&shmbuf_right);
		shmbuf_destroy(&shmbuf_depth);
		shmbuf_destroy(&shmbuf_sobel);
		pthread_mutex_destroy(&mtx_buf);
		zed.close();
	}

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
			pthread_mutex_lock(&mtx_buf);
			if(fl_left) shmbuf_load(cv_left,&shmbuf_left);
			if(fl_right) shmbuf_load(cv_right,&shmbuf_right);
			if(fl_depth) shmbuf_load(cv_depth,&shmbuf_depth);
			if(fl_sobel) shmbuf_load(cv_sobel,&shmbuf_sobel);
			pthread_mutex_unlock(&mtx_buf);
printf("shared buffers loaded\n");

			//cv::imshow("Left View",cv_left);
			//cv::imshow("Sobel Filter",cv_sobel);
			//cv::waitKey(30);
		}framedelay.tv_sec=0;
		framedelay.tv_nsec=10000000;
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
