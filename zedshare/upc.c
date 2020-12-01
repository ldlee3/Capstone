/*On-board Communication Interface: upc.c
	Chandra Boyle
	
	Implements callback interface for UNIX socket server and client.
*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/types.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <signal.h>
#include <errno.h>
#include <time.h>

#include "upc.h"

#define DEBUG

#ifdef DEBUG
#define DBGMSG(x)	{ fprintf(stderr,"ERROR in %s:%d, %s\n",__FILE__,__LINE__,x); }
#define DBGMSGE(x)	{ int errv=errno; fprintf(stderr,"ERROR in %s:%d, %s(%d), %s\n",__FILE__,__LINE__,strerror(errv),errv,x); }

#else
#define DBGMSG
#define DBGMSGE

#endif

#define UPC_MSGBLK	((size_t)512)
#define UPC_PATHPAD	32
#define UPC_FMODE	((mode_t)0666)

const char UPC_DEFROOT[]="~/rover/";
const char UPC_DIRCOMM[]="comm/";
const char UPC_DIRLOGS[]="logs/";
const char UPC_EXTSOCK[]=".sock";
const char UPC_EXTPIPE[]=".fifo";
const char UPC_EXTLOGS[]=".log";
const char UPC_LOGPFIX[]="upc_";

struct upc_cli;

struct upc_cli{
	pthread_t thread;
	int sock;
	char *buf;
	size_t bufsz,buflen;
	struct upc_inst *inst;
	struct upc_cli *next,*prev;
};

struct upc_conn{
	char *name;
	int sock;
	pthread_mutex_t mtx;
};

struct upc_inst{
	char name[UPC_MAXNAME+1];
	char *root;
	pthread_t thread;
	int sock,logfd,logcl;
	char *(*cmdh)(const char*);
	void (*msgh)(const char*);
	unsigned int maxcli,clict;
	pthread_mutex_t mtx_cli,mtx_log;
	pthread_cond_t cond_maxcli;
	struct upc_cli *clilist;
};

void upc_log(struct upc_inst *upc_data, const char *msg);
void *upc_cmdh(struct upc_cli *cli);
void *upc_main(struct upc_inst *upc_data);

//error message format: [timestamp]{thread #}@upc.c:line# in function upc_function(), errnoname(errno int) in call to error'd func, error description
//fprintf(STDERR_FILENO,"[%ld]@%s:%d in function %s(), thread %d with error %s(%d): %s\n",time(),__FILE__,__LINE__,FUNCNAME,THREAD#,ERRNONAME,errno_saved,DESCRIPTIONSTRING)

void upc_log(struct upc_inst *upc_data, const char *msg)
{
	size_t msglen,msgcur;
	ssize_t msgwr;
	char buf[UPC_PATHPAD];
	time_t tm;
	
	tm=time(NULL);
	pthread_mutex_lock(&(upc_data->mtx_log));
	msglen=snprintf(buf,UPC_PATHPAD,"[%ld] ",(long)tm);
	msgcur=0;
	while((msgcur+=(msgwr=write(upc_data->logfd,buf+msgcur,msglen-msgcur)))<msglen) if(msgwr<0){
		pthread_mutex_unlock(&(upc_data->mtx_log));
		return;
	}msglen=strlen(msg);
	msgcur=0;
	while((msgcur+=(msgwr=write(upc_data->logfd,msg+msgcur,msglen-msgcur)))<msglen) if(msgwr<0){
		pthread_mutex_unlock(&(upc_data->mtx_log));
		return;
	}strcpy(buf,"\n");
	msglen=2;
	msgcur=0;
	while((msgcur+=(msgwr=write(upc_data->logfd,msg+msgcur,msglen-msgcur)))<msglen) if(msgwr<0){
		pthread_mutex_unlock(&(upc_data->mtx_log));
		return;
	}pthread_mutex_unlock(&(upc_data->mtx_log));
}

char *upc_sendcmd(const char *root, const char *dest, const char *cmd)
{
	struct sockaddr_un addr;
	int cmdsock;
	int rootfd,commfd;
	int rootlen,pathterm;
	
	if(root==NULL) root=UPC_DEFROOT;
	rootlen=strlen(root);
	pathterm=(rootlen>0)&&(root[rootlen-1]!='/');
	
	//argument validation
	if(*dest=='\0'){
		DBGMSG("dest in upc_send empty")
		return NULL;
	}if(strlen(dest)>UPC_MAXNAME){
		DBGMSG("dest in upc_send longer than UPC_MAXNAME")
		return NULL;
	}if((rootlen+pathterm+strlen(UPC_DIRCOMM)+strlen(dest)+strlen(UPC_EXTSOCK))>=sizeof(addr.sun_path)){
		DBGMSG("socket path in upc_send longer than can fit in sockaddr_un.sun_path")
		return NULL;
	}
	
	//directory validation
	if((rootfd=open(root,O_RDONLY|O_DIRECTORY|O_PATH|O_CLOEXEC))<0){
		return NULL;
	}if((commfd=openat(rootfd,UPC_DIRCOMM,O_RDONLY|O_DIRECTORY|O_CLOEXEC))<0){
		close(rootfd);
		return NULL;
	}close(rootfd);
	close(commfd);
	
	//socket connection
	addr.sun_family=AF_UNIX;
	strcpy(addr.sun_path,root);
	if(pathterm){ addr.sun_path[rootlen]='/'; addr.sun_path[rootlen+1]='\0'; }
	strcat(addr.sun_path,UPC_DIRCOMM);
	strcat(addr.sun_path,dest);
	strcat(addr.sun_path,UPC_EXTSOCK);
	if((cmdsock=socket(AF_UNIX,SOCK_STREAM,0))<0){
		return NULL;
	}if(connect(cmdsock,(struct sockaddr*)&addr,sizeof(struct sockaddr_un))<0){
		close(cmdsock);
		return NULL;
	}
	
	char *buf;
	size_t bufsz,buflen,bufcur=0;
	ssize_t bufwr;
	
	buflen=strlen(cmd)+1;
	while((bufcur+=(bufwr=write(cmdsock,cmd+bufcur,buflen-bufcur)))<buflen) if(bufwr<0){
		//error
		close(cmdsock);
		return NULL;
	}
	
	buflen=bufcur=0;
	if((buf=(char*)malloc((bufsz=1)*UPC_MSGBLK))==NULL){
		//error
		close(cmdsock);
		return NULL;
	}while((bufwr=read(cmdsock,buf+buflen,bufsz*UPC_MSGBLK-buflen))!=0){
		if(bufwr<0){
			//error
			free(buf);
			close(cmdsock);
			return NULL;
		}buflen+=bufwr;
		while(bufcur<buflen) if(buf[bufcur++]=='\0'){
			close(cmdsock);
			return buf;
		}bufsz=buflen/UPC_MSGBLK+1;
		if((buf=(char*)realloc(buf,bufsz*UPC_MSGBLK))==NULL){
			//error
			pthread_exit(NULL);
		}
	}
	
	close(cmdsock);
	return NULL;
}

//check threadid in upc_stop to prevent calls from child threads? (cli,msg,...) (deadlock: waiting to join child in child)

void upc_stop(struct upc_inst *upc_data)
{
	struct sockaddr_un addr;
	void *rval;
	
	pthread_cancel(upc_data->thread);
	pthread_join(upc_data->thread,&rval);
	
	close(upc_data->sock);
	strcpy(addr.sun_path,upc_data->root);
	strcat(addr.sun_path,UPC_DIRCOMM);
	strcat(addr.sun_path,upc_data->name);
	strcat(addr.sun_path,UPC_EXTSOCK);
	unlink(addr.sun_path);
	if(upc_data->logcl) close(upc_data->logfd);
	pthread_cond_destroy(&(upc_data->cond_maxcli));
	pthread_mutex_destroy(&(upc_data->mtx_log));
	pthread_mutex_destroy(&(upc_data->mtx_cli));
	free(upc_data->root);
	free(upc_data);
}

void upc_cmdh_cleanup(struct upc_cli *cli)
{
	free(cli->buf);
	close(cli->sock);
	pthread_mutex_lock(&(cli->inst->mtx_cli));
	if(cli->prev==NULL) cli->inst->clilist=cli->next;
	else cli->prev->next=cli->next;
	if(cli->next!=NULL) cli->next->prev=cli->prev;
	if((cli->inst->clict--)==cli->inst->maxcli) pthread_cond_signal(&(cli->inst->cond_maxcli));
	pthread_mutex_unlock(&(cli->inst->mtx_cli));
	free(cli);
}

void *upc_cmdh(struct upc_cli *cli)
{
	size_t bufcur=0;
	ssize_t bufrd;
	char *reply;
	
	//block all signals except sigalrm?
	pthread_cleanup_push((void (*)(void*))&upc_cmdh_cleanup,(void*)cli);
	
	if((cli->buf=(char*)malloc((cli->bufsz=1)*UPC_MSGBLK))==NULL){
		//error
		pthread_exit(NULL);
	}while((bufrd=read(cli->sock,cli->buf+cli->buflen,cli->bufsz*UPC_MSGBLK-cli->buflen))!=0){
		if(bufrd<0){
			//error
			pthread_exit(NULL);
		}cli->buflen+=bufrd;
		while(bufcur<cli->buflen) if(cli->buf[bufcur++]=='\0'){
			size_t rsplen,rspcur=0;
			ssize_t rspwr;
			
			if((reply=cli->inst->cmdh(cli->buf))==NULL){
				//error
				pthread_exit(NULL);//?
			}rsplen=strlen(reply)+1;
			while((rspcur+=(rspwr=write(cli->sock,reply+rspcur,rsplen-rspcur)))<rsplen) if(rspwr<0){
				//error
				pthread_exit(NULL);
			}free(reply);//prevents use of statically allocated strings, reconsider approach?
			
			memmove(cli->buf,cli->buf+bufcur,cli->buflen-bufcur);
			cli->buflen-=bufcur;
			bufcur=0;
		}cli->bufsz=cli->buflen/UPC_MSGBLK+1;
		if((cli->buf=(char*)realloc(cli->buf,cli->bufsz*UPC_MSGBLK))==NULL){
			//error
			pthread_exit(NULL);
		}
	}
	
	pthread_cleanup_pop(1);
	return NULL;
}

void upc_main_cleanup2(struct upc_inst *upc_data)
{
	pthread_mutex_unlock(&(upc_data->mtx_cli));
}

void upc_main_cleanup(struct upc_inst *upc_data)
{
	pthread_t thread;
	void *rval;
	
	while(pthread_mutex_lock(&(upc_data->mtx_cli)),upc_data->clilist!=NULL){
		thread=upc_data->clilist->thread;
		pthread_cancel(thread);
		pthread_mutex_unlock(&(upc_data->mtx_cli));
		pthread_join(thread,&rval);
	}pthread_mutex_unlock(&(upc_data->mtx_cli));
}

void *upc_main(struct upc_inst *upc_data)
{
	struct upc_cli *cli;
	int clsock;
	
	//block all signals except sigalrm?
	pthread_cleanup_push((void (*)(void*))&upc_main_cleanup,(void*)upc_data);
	
	while(1){
		if(upc_data->maxcli>0){
			pthread_mutex_lock(&(upc_data->mtx_cli));
			pthread_cleanup_push((void (*)(void*))&upc_main_cleanup2,(void*)upc_data);
			if(upc_data->clict>=upc_data->maxcli) pthread_cond_wait(&(upc_data->cond_maxcli),&(upc_data->mtx_cli));
			pthread_cleanup_pop(1);
		}if((clsock=accept(upc_data->sock,NULL,NULL))<0){
			//send error msg
			pthread_exit(NULL);
		}if((cli=(struct upc_cli*)malloc(sizeof(struct upc_cli)))==NULL){
			//send error msg
			close(clsock);
			pthread_exit(NULL);
		}cli->sock=clsock;
		cli->prev=NULL;
		cli->inst=upc_data;
		cli->buf=NULL;
		cli->bufsz=cli->buflen=0;
		pthread_mutex_lock(&(upc_data->mtx_cli));
		if((errno=pthread_create(&(cli->thread),NULL,(void *(*)(void*))&upc_cmdh,(void*)cli))!=0){
			pthread_mutex_unlock(&(upc_data->mtx_cli));
			//send error msg
			free(cli);
			close(clsock);
			pthread_exit(NULL);
		}if(upc_data->clilist!=NULL) upc_data->clilist->prev=cli;
		cli->next=upc_data->clilist;
		upc_data->clilist=cli;
		upc_data->clict++;
		pthread_mutex_unlock(&(upc_data->mtx_cli));
	}
	
	pthread_cleanup_pop(1);
	return (void*)upc_data;
}

struct upc_inst *upc_init(const char *root, const char *name, char *(*cmdh)(const char*), void (*msgh)(const char*), int logfd, unsigned int maxcli)
{
	struct sockaddr_un addr;
	int cmdsock,logcl;
	int rootfd,commfd,logsfd;
	int rootlen,pathterm;
	struct upc_inst *upc_data;
	
	if(root==NULL) root=UPC_DEFROOT;
	rootlen=strlen(root);
	pathterm=(rootlen>0)&&(root[rootlen-1]!='/');
	
	//argument validation
	if(*name=='\0'){
		DBGMSG("name in upc_init empty")
		return NULL;
	}if(strlen(name)>UPC_MAXNAME){
		DBGMSG("name in upc_init longer than UPC_MAXNAME")
		return NULL;
	}if((rootlen+pathterm+strlen(UPC_DIRCOMM)+strlen(name)+strlen(UPC_EXTSOCK))>=sizeof(addr.sun_path)){
		DBGMSG("socket path in upc_init longer than can fit in sockaddr_un.sun_path")
		return NULL;
	}if(cmdh==NULL || msgh==NULL){
		DBGMSG("null cmd handler in upc_init")
		return NULL;
	}
	
	//directory validation and creation
	if((rootfd=open(root,O_RDONLY|O_DIRECTORY|O_PATH|O_CLOEXEC))<0){
		return NULL;
	}if((mkdirat(rootfd,UPC_DIRLOGS,UPC_FMODE))<0 && errno!=EEXIST){
		close(rootfd);
		return NULL;
	}if((logsfd=openat(rootfd,UPC_DIRLOGS,O_RDONLY|O_DIRECTORY|O_CLOEXEC))<0){
		close(rootfd);
		return NULL;
	}if((mkdirat(rootfd,UPC_DIRCOMM,UPC_FMODE))<0 && errno!=EEXIST){
		close(logsfd);
		close(rootfd);
		return NULL;
	}if((commfd=openat(rootfd,UPC_DIRCOMM,O_RDONLY|O_DIRECTORY|O_CLOEXEC))<0){
		close(logsfd);
		close(rootfd);
		return NULL;
	}close(rootfd);
	
	//duplicate instance check, socket creation
	addr.sun_family=AF_UNIX;
	strcpy(addr.sun_path,root);
	if(pathterm){ addr.sun_path[rootlen]='/'; addr.sun_path[rootlen+1]='\0'; }
	strcat(addr.sun_path,UPC_DIRCOMM);
	strcat(addr.sun_path,name);
	strcat(addr.sun_path,UPC_EXTSOCK);
	if(flock(commfd,LOCK_EX)<0){
		close(logsfd);
		goto _cleanup0;
	}if((cmdsock=socket(AF_UNIX,SOCK_STREAM,0))<0){
		close(logsfd);
		goto _cleanup1;
	}if(bind(cmdsock,(struct sockaddr*)&addr,sizeof(struct sockaddr_un))<0){
		close(logsfd);
		goto _cleanup2;
	}
	
	//logfile creation
	if(logfd<0){
		char pathbuf[UPC_MAXNAME+UPC_PATHPAD];
		strcpy(pathbuf,UPC_LOGPFIX);
		strcat(pathbuf,name);
		strcat(pathbuf,UPC_EXTLOGS);
		if((logfd=openat(logsfd,pathbuf,O_RDWR|O_CREAT|O_TRUNC|O_CLOEXEC,UPC_FMODE))<0){
			close(logsfd);
			goto _cleanup3;
		}logcl=1;
	}else logcl=0;
	close(logsfd);
	
	//instance struct allocation
	if((upc_data=(struct upc_inst*)malloc(sizeof(struct upc_inst)))==NULL){
		goto _cleanup4;
	}if((upc_data->root=(char*)malloc(rootlen+pathterm+1))==NULL){
		goto _cleanup5;
	}strcpy(upc_data->root,root);
	if(pathterm){ upc_data->root[rootlen]='/'; upc_data->root[rootlen+1]='\0'; }
	strcpy(upc_data->name,name);
	upc_data->sock=cmdsock;
	upc_data->logcl=logcl;
	upc_data->logfd=logfd;
	upc_data->maxcli=maxcli;
	upc_data->cmdh=cmdh;
	upc_data->msgh=msgh;
	upc_data->clict=0;
	upc_data->clilist=NULL;
	if((errno=pthread_mutex_init(&(upc_data->mtx_cli),NULL))!=0){
		goto _cleanup6;
	}if((errno=pthread_mutex_init(&(upc_data->mtx_log),NULL))!=0){
		goto _cleanup7;
	}if((errno=pthread_cond_init(&(upc_data->cond_maxcli),NULL))!=0){
		goto _cleanup8;
	}
	
	//listen socket and start server thread
	if(listen(upc_data->sock,1)<0){
		goto _cleanup9;
	}if((errno=pthread_create(&(upc_data->thread),NULL,(void *(*)(void*))&upc_main,(void*)upc_data))!=0){
		goto _cleanup9;
	}flock(commfd,LOCK_UN);
	close(commfd);
	
	return upc_data;
	
_cleanup9:
	pthread_cond_destroy(&(upc_data->cond_maxcli));
_cleanup8:
	pthread_mutex_destroy(&(upc_data->mtx_log));
_cleanup7:
	pthread_mutex_destroy(&(upc_data->mtx_cli));
_cleanup6:
	free(upc_data->root);
_cleanup5:
	free(upc_data);
_cleanup4:
	if(logcl) close(logfd);
_cleanup3:
	unlink(addr.sun_path);
_cleanup2:
	close(cmdsock);
_cleanup1:
	flock(commfd,LOCK_UN);
_cleanup0:
	close(commfd);
	return NULL;
}
