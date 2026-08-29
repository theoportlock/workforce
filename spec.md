Workforce creates and runs commands in the order of a directed graph.
Similar to Galaxy workflow, Qiime plugin workflows, AnADMA2, Snakemake, Nextflow, Make
Supports multiuser editing/running
All operations that can be done on the frontend web interface should be possible on the CLI
An execution can be performed on either the full graph or a subgraph.


# cli
<workfile> = graphml file
<worksession> = file or worksession; if is file then load server first (wf load); export WORKFORCE_WORKSESSION=<workfile> # Default url
<url> = export WORKFORCE_URL='127.0.0.1:5049' # Default url
<cmd> = command as string

---- not requests ----
workforce start # Starts the server in background
workforce start --foreground # Attempts to start the server at <url>
---- requests ----
workforce stop # Attempts to stops the server running at <url> env variable with shutdown request
workforce # Launch webapp
workforce run <worksession> # Runs the worksession. Uses load with autounload argument that will unload when finished/error?
workforce <worksession> # Runs the worksession
workforce run <worksession> --nodes node1 # Runs the worksession with the specific nodes
workforce run <worksession> --wrapper 'docker run image bash -c "{}"' # Runs the worksession with the specific wrapper
workforce run <worksession> --group <groupid> # Runs the worksession with the specific wrapper
workforce ls # Views worksessions on server and URL
workforce ls <worksession> # Views nodes and edges of worksession with their IDs
workforce ls nodes/edges <worksession> # Views nodes/edges of worksession with their IDs
workforce ls nodes --id 'filtering_of_data' <worksession> # Views node/edge information (including logs)
workforce ls groups <worksession> # Views defined groups of nodes
workforce ls wrapper <worksession> # Views nodes/edges of worksession with their IDs
workforce load <workfile> # Adds workfile to server
workforce load <workfile> --autounload # Adds workfile to server and waits for unload signal (from runs) and unloads
workforce load <workfile> -name 'test_work' # Adds workfile to server then does a set name request to set name of worksession (if that name is available)
workforce unload <worksession> # Adds workfile to server
workforce add node <worksession> <cmd> -x 100 -y 200 # Adds node to worksession and prints the node ID
workforce add node <worksession> <cmd> --id 'filtering_of_data' -x 100 -y 200 # Adds node to worksession and prints the node ID. If the ID is given the has to be unique (check)
workforce add node <worksession> <cmd> --id 'filtering_of_data' --after 'quality_check' -x +100 # Adds node then draws edge from another node
workforce add edge <worksession> <src> <tgt> --blocking # adds edge (blocking is default)
workforce add group <worksession> <nodeIDs> # adds nodes to group
workforce edit node status <worksession> <id> "run" # Changes node status
workforce edit node command <worksession> <id> "echo test" # Changes node command
workforce edit node name <worksession> <id> "run" # Changes session name
workforce edit edge type <worksession> <id> --blocking/--nonblocking # Changes edge to blocking or non-blocking
workforce edit wrapper <worksession> 'docker run image bash -c "{}"' # Changes session name
workforce cp <worksession> <group or nodeids> <worksession>
workforce new <workfile> # Creates a new session; if it's a path then create blank then load
workforce save <worksession> <workfile> # Saves the session to a workfile and relinks session to that workfile
workforce ps # list currently running nodes in queue (accepts workfile or not)
workforce top <worksession> -n 2 # Same as workforce ps but with watch

# frontend
index has ability to load/unload workfiles into worksessions
Each worksession page is a node and edge editor in react flow frontend
double click node to edit node (command) contents
double click on empty portion of the canvas to add node
right click and drag on one node to another to draw edges between nodes
shift right click and drag to draw non-blocking edges (can also double click edge or right click on the edge)
r to trigger node run
d to delete selected node(s)
w for wrapper
e to edit node
c to clear

# run
If a subset is defined, a subgraph is built from those nodes, and if no subset is given but specific nodes are selected (as specified as a selected argument which is loaded from the frontend also), the full graph run starts (changes status to 'run') from those selected nodes instead of from nodes with in-degree 0.
If neither applies, start nodes default to those with in-degree 0 in the relevant graph.
This 'run' status change request is emitted which triggers the execution of that node with the status change to 'running'.
When a node runs, its stdout and stderr are captured as node attributes, and on successful completion an event of changing status to 'ran' is emitted only to that specific run task using its client/run ID (as with the other emissions).
The scheduler then marks all outgoing edges from the completed node as 'ready', and each such status change triggers and emit that triggers a check on the target node; when all its incoming edges are 'ready', those edge flags are cleared, the node’s status becomes 'run', and execution continues recursively following the same cycle.
In the frontend, the run is triggered with the 'r' key.
If nodes are selected, the run starts from those nodes.
If no nodes are selected, the run starts from the in-degree 0 nodes (roots).
Accepts a list of selected nodes that a subgraph should be made from.
If no nodes are selected (this can be specified by cli or frontend), then failed nodes are selected.
If there are no failed nodes then the nodes with 0 in degree are started.
NO1 When a node is ran, it's pid, error code. stdout and err are captured as a node attribute (viewable from the frontend with shortcut) and, if node is successfully completed, an event is emitted to that run request (with a client id so that multiple run and frontend clients can be ran concurrently).
That emission will trigger a scheduler which will request the map (network and the filtered to subnetwork if subset run).
It will look at all outgoing edges and set them as 'ready' emitting this edge status change.
This emit should trigger an event that looks at the target node to see if all of its incoming edges are set to ready and, if they are, the node's status is changed to 'run', status is removed from those edges and loops back around to NO1.
There are blocking and non-blocking edges
all incoming blocking edges must be marked as ready before the target node can be executed
