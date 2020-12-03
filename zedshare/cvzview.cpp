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

#include "upc.h"

int flag;

void sig_h(int s){
        printf("sigint\n");
        flag=0;
}

#define BUF_WIDTH	1280
#define BUF_HEIGHT	720
#define BUF_DEPTH	4

int main(int argc, char **argv)
{
	size_t bufsz=BUF_WIDTH*BUF_HEIGHT*BUF_DEPTH;
	int shm,fv,frame=-1;
	uchar *shm_map;
	char *reply;
	char *shmname;
	char cmdbuf[128];
	cv::Mat mat(BUF_HEIGHT,BUF_WIDTH,CV_8UC4);
	
	signal(SIGINT,sig_h);
	
	if(argc!=2){
		shm_unlink("shm_zedleft");
		shm_unlink("shm_zedright");
		shm_unlink("shm_zeddepth");
		shm_unlink("shm_cvsobel");
		return 0;
	}if(!strcmp(argv[1],"shm_zedleft")) shmname="left";
	else if(!strcmp(argv[1],"shm_zedright")) shmname="right";
	else if(!strcmp(argv[1],"shm_zeddepth")) shmname="depth";
	else if(!strcmp(argv[1],"shm_cvsobel")) shmname="sobel";
	else return 1;
	
	if((shm=shm_open(argv[1],O_RDONLY|O_CLOEXEC,(mode_t)0777))==-1) return 1;
	if((shm_map=(uchar*)mmap(NULL,bufsz,PROT_READ,MAP_SHARED,shm,0))==MAP_FAILED){
		close(shm);
		return 1;
	}
	
	flag=1;
	strcpy(cmdbuf,"set "); strcat(cmdbuf,shmname); strcat(cmdbuf," up");
	if((reply=upc_sendcmd("/home/nvidia/roverupc","cvzshare",cmdbuf))==NULL || strcmp(reply,"ACK")){
		free(reply);
		munmap(shm_map,bufsz);
		close(shm);
		return 1;
	}free(reply);
	//struct timespec fdel;
	while(flag){
		strcpy(cmdbuf,"read "); strcat(cmdbuf,shmname); strcat(cmdbuf," lock");
		if((reply=upc_sendcmd("/home/nvidia/roverupc","cvzshare",cmdbuf))==NULL) break;
		if(!strcmp(reply,"DOWN") || !strcmp(reply,"UNKNOWN")){
			free(reply);
			break;
		}else{
			char tmp[16];
			printf("reply: %s\n",reply);
			strncpy(tmp,reply,16);
			tmp[3]='\0'; tmp[15]='\0';
			if(strcmp(tmp,"ACK")){
				free(reply);
				break;
			}fv=atoi(tmp+4);
		}free(reply);
		//printf("lock acquired\n");
		if(fv!=frame){
			frame=fv;
			memcpy(mat.data,shm_map,bufsz);
			printf("frame loaded\n");
		}strcpy(cmdbuf,"read "); strcat(cmdbuf,shmname); strcat(cmdbuf," release");
		if((reply=upc_sendcmd("/home/nvidia/roverupc","cvzshare",cmdbuf))==NULL) break;
		free(reply);
		//printf("lock released\n");
		cv::imshow(argv[1],mat);
		cv::waitKey(10);
		//fdel.tv_sec=0;
		//fdel.tv_nsec=20000000;
		//nanosleep(&fdel,NULL);
	}
	
	munmap(shm_map,bufsz);
	close(shm);
}
