#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <semaphore.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>

#include "shmbuf.h"

void shmbuf_read_lock(struct shmbuf *sbuf)
{
	while(sem_wait(&(sbuf->sem)),sbuf->wf) sem_post(&(sbuf->sem));
	sbuf->rf++;
	sem_post(&(sbuf->sem));
}

void shmbuf_read_release(struct shmbuf *sbuf)
{
	sem_wait(&(sbuf->sem));
	if(sbuf->rf) sbuf->rf--;
	sem_post(&(sbuf->sem));
}

void shmbuf_write_lock(struct shmbuf *sbuf)
{
	while(sem_wait(&(sbuf->sem)),sbuf->wf) sem_post(&(sbuf->sem));
	sbuf->wf=1;
	sem_post(&(sbuf->sem));
	while(sem_wait(&(sbuf->sem)),sbuf->rf) sem_post(&(sbuf->sem));
	sem_post(&(sbuf->sem));
}

void shmbuf_write_release(struct shmbuf *sbuf)
{
	sem_wait(&(sbuf->sem));
	sbuf->wf=0;
	sem_post(&(sbuf->sem));
}

void shmbuf_destroy(struct shmbuf *sbuf){
	sem_destroy(&(sbuf->sem));
	munmap(sbuf->buf,sbuf->bufsz);
	close(sbuf->shm);
	shm_unlink(sbuf->shmname);
	free(sbuf->shmname);
}

int shmbuf_init(struct shmbuf *sbuf, const char *name, size_t size)
{
	sbuf->wf=0;
	sbuf->rf=0;
	sbuf->frame=0;
	sbuf->bufsz=size;
	if((sbuf->shmname=(char*)malloc(strlen(name)+1))==NULL) return -1;
	strcpy(sbuf->shmname,name);
	
	if((sbuf->shm=shm_open(sbuf->shmname,O_RDWR|O_CREAT|O_EXCL,(mode_t)0666))==-1){
		free(sbuf->shmname);
		return -1;
	}if(ftruncate(sbuf->shm,sbuf->bufsz)==-1){
		close(sbuf->shm);
		shm_unlink(sbuf->shmname);
		free(sbuf->shmname);
		return -1;
	}if((sbuf->buf=(unsigned char*)mmap(NULL,sbuf->bufsz,PROT_READ|PROT_WRITE,MAP_SHARED,sbuf->shm,0))==MAP_FAILED){
		close(sbuf->shm);
		shm_unlink(sbuf->shmname);
		free(sbuf->shmname);
		return -1;
	}if((sem_init(&(sbuf->sem),0,1))==-1){
		munmap(sbuf->buf,sbuf->bufsz);
		close(sbuf->shm);
		shm_unlink(sbuf->shmname);
		free(sbuf->shmname);
		return -1;
	}
	
	return 0;
}
