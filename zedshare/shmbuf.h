struct shmbuf{
	char *shmname;
	int shm;
	size_t bufsz;
	unsigned char *buf;
	volatile char rf,wf;
	unsigned int frame;
	sem_t sem;
};

int shmbuf_init(struct shmbuf *sbuf, const char *name, size_t size);
void shmbuf_destroy(struct shmbuf *sbuf);

void shmbuf_read_lock(struct shmbuf *sbuf);
void shmbuf_read_release(struct shmbuf *sbuf);
void shmbuf_write_lock(struct shmbuf *sbuf);
void shmbuf_write_release(struct shmbuf *sbuf);
