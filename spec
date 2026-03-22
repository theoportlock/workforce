# cli
workforce #Launch GUI
workforce gui <file.graphml> #Launch GUI
workforce run <workfile> # Runs the workfile
workforce <workfile> # Runs the workfile
workforce run <workfile> --nodes node1 # Runs the workfile with the specific nodes
workforce run <workfile> --wrapper 'docker run image bash -c "{}"' # Runs the workfile with the specific wrapper
workforce server start # Starts the server (singleton)
workforce server start --foreground # Starts the server
workforce server stop # Stops the server (singleton)
workforce server ls # Views worksessions on server
workforce edit add-node <file> "cmd" --x 100 --y 200 # Adds node to workfile and prints the node ID
var=$(wf edit add-node <file> "cmd" --x 100 --y 200) # saves node ID to var that can be used to add edge
workforce edit add-edge <file> <src> <tgt> # adds edge
workforce edit edit-status <file> node <id> "run" # Changes node status
workforce edit new <file> # Creates a new workfile at that location

# gui
node and edge editor in react flow frontend
double click node to edit node (command) contents
double click on empty portion of the canvas to add node
right click and drag on one node to another to draw edges between nodes
shift right click and drag to draw non-blocking edges
r to trigger node run
d to delete selected node(s)
w for wrapper
e to edit node
o to open worksession from file

# run
Accepts a list of selected nodes that a subgraph should be made from.
If no nodes are selected (this can be specified by cli or GUI to use API request), then failed nodes are selected.
If there are no failed nodes then the nodes with 0 in degree are started.
NO1 When a node is ran, it's pid, error code. stdout and err are captured as a node attribute (viewable from the gui with shortcut) and, if node is successfully completed, an event is emitted to that run request (with a client id so that multiple run and gui clients can be ran concurrently).
That emission will trigger a scheduler which will request the map (network and the filtered to subnetwork if subset run).
It will look at all outgoing edges and set them as 'ready' emitting this edge status change.
This emit should trigger an event that looks at the target node to see if all of its incoming edges are set to ready and, if they are, the node's status is changed to 'run', status is removed from those edges and loops back around to NO1.

# Server
On server start (using __main__.py cli), it first checks to see if the Workfile (abs path) has been assigned a URL (stored in a shared Registry file, The Registry manages a list of workfiles and their URLs)
If not, a flask API server for a URL (or given on cli - conditional if the given URL doesnt exist) unique to the Workfile is started and stored in the Registry if successfully started.
In the Registry the client count is started at  1, and PID is stored
On server stop, fail all the running processes, remove Workfile + URL from Registry (heartbeat?)
Accepts requests to modify the Workfile using edit
Accepts requests to run Workfile using run, that will start run clients.
This request accepts the run arguments of subgraph, selected, and wrapper
