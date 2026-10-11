Workforce creates and runs commands in the order of a directed graph.
Similar to Galaxy workflow, Qiime plugin workflows, AnADMA2, Snakemake, Nextflow, Make
Supports multiuser editing/running
All operations that can be done on the frontend web interface should be possible on the CLI
An execution can be performed on either the full graph or a subgraph.


# cli
<workfile> = graphml file
<workspace> = file or workspace; if is file then load server first (workforce load); export WORKFORCE_WORKspace=<workfile> # Default url
<url> = export WORKFORCE_URL='127.0.0.1:5049' # Default url
<cmd> = command as string

---- not requests ----
workforce # Launches help
workforce server up # Starts the server in background
workforce server up --foreground # Attempts to start the server at <url>
---- requests ----
workforce server down # Attempts to stops the server running at <url> env variable with shutdown request
workforce server open <workfile> # loads a workfile into the server
workforce # Launch webapp
workforce status # Views workspace on server and URL
workforce space run <workspace> # Runs the workspace. Uses load with autounload argument that will unload when finished/error?
workforce <workspace> # Runs the workspace
workforce space run <workspace> --nodes node1 # Runs the workspace with the specific nodes
workforce space run <workspace> --wrapper 'docker run image bash -c "{}"' # Runs the workspace with the specific wrapper
workforce space run <workspace> --group <groupid> # Runs the workspace with the specific wrapper
workforce space run <workspace> --until node1 # Runs the workspace from indegree=0 to node1
workforce space run <workspace> --from node1 node2 # Runs the workspace node(s) to outdegree=0
workforce space stop # Attempts to stop the current processes
workforce space stop --node node1 node2 # Attempts to stop the current processes for those nodes
workforce space stop --group group1 # Attempts to stop the current processes for those nodes in that group
workforce wrapper ls <workspace> # Views nodes/edges of workspace with their IDs
workforce wrapper edit <workspace> 'docker run image bash -c "{}"' # Changes space name
workforce space load <workfile> # Adds workfile to server
workforce space load -r <workfiles> # like pip install -r, recursively loads workfiles to server from list
workforce space load <workfile> --autounload # Adds workfile to server and waits for unload signal (from runs) and unloads
workforce space load <workfile> -name 'test_work' # Adds workfile to server then does a set name request to set name of workspace (if that name is available)
workforce space unload <workspace> # Removes workfile from server
workforce node add <workspace> <cmd> -x 100 -y 200 # Adds node to workspace and prints the node ID
workforce node add <workspace> <cmd> --id 'filtering_of_data' -x 100 -y 200 # Adds node to workspace and prints the node ID. If the ID is given the has to be unique (check)
workforce node add <workspace> <cmd> --id 'filtering_of_data' --after 'quality_check' -x +100 # Adds node then draws edge from another node (default is +100 in x)
workforce node edit status <workspace> <id> "run" # Changes node status
workforce node edit command <workspace> <id> "echo test" # Changes node command AND CLEAR THE LOG
workforce node edit name <workspace> <id> "run" # Changes space name
workforce node ls <workspace> # Views nodes of workspace with their IDs
workforce node status --id 'filtering_of_data' <workspace> # Views node/edge information (including logs)
workforce edge add <workspace> <src> <tgt> --blocking # adds edge (blocking is default)
workforce edge edit type <workspace> <id> --blocking/--nonblocking # Changes edge to blocking or non-blocking
workforce edge ls <workspace> # Views edges of workspace with their IDs
workforce group add <workspace> <nodeIDs> # adds nodes to group
workforce group ls <workspace> # Views defined groups of nodes
workforce group rm <workspace> <groupID> # Views defined groups of nodes
workforce space new <workspace> # Creates a new space; if it's a path then create blank then load - alias as just workforce new
workforce space save <workspace> <workfile> # Saves the space to a workfile and relinks space to that workfile - alisas as just workforce save
workforce space ps # list currently running nodes in queue (accepts workfile or not)
workforce server ps # list currently running nodes in queue (accepts workfile or not)
workforce server top <workspace> -n 2 # Same as workforce ps but with watch

workforce node open <workfile> --id 'filtering_of_data' # loads all instances of .wf in the nodes command into the server

# frontend
index has ability to load/unload workfiles into workspace
Each workspace page is a node and edge editor in react flow frontend
double click node to edit node (command) contents
double click on empty portion of the canvas to add node
click and drag from the right handle (source) to the left handle (target) to draw edges between nodes (blocking by default)
shift right click and drag to draw non-blocking edges (can also double click edge or right click on the edge)
r to trigger node run
d to delete selected node(s)
w for wrapper
e to edit node
c to clear
o on a selected node does a regex for .wf files in the nodes command and opens them with the same function that is called by workforce edit 

# run
running from cli can look like

species_correlation.wf \
  -i results/species.tsv \
  -o results/species_correlation

or
species_correlation.wf \
  -i results/species.tsv

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
