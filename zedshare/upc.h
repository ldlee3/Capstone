/*On-board Communication Interface: upc.h
	Chandra Boyle
	
	Implements callback interface for UNIX socket server and simple client.
	
	upc_init creates an unix socket in root/comm/name.sock if it does not exist and starts a threaded server to handle connections to it
		a pointer to a upc_inst is returned which serves as a reference to the server object
		the function cmdh passed in is a callback to handle incoming messages
		msgh is an error handling callback to notify the application of asynchronous failure in the server threads
	upc_stop is called with the upc_inst to bring down the server and unlink the socket
	
	upc_sendcmd does not depend on upc_init being called and serves as a client to the socket in root/comm/dest.sock, sending the single message cmd, returning the response, and closing the connection
*/

//defines
#define UPC_MAXNAME	15

//types
struct upc_inst;
//struct upc_conn;

//func protos
struct upc_inst *upc_init(const char *root, const char *name, char *(*cmdh)(const char*), void (*msgh)(const char*), int logfd, unsigned int maxcli);
void upc_stop(struct upc_inst *upc_data);

char *upc_sendcmd(const char *root, const char *dest, const char *cmd);

//int upc_cmdopen(char *dest);
//int upc_cmdclose(char *dest);