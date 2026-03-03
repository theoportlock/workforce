wf											Launch GUI
wf gui <file.graphml>									Launch GUI
wf run <workfile>									Run
wf <workfile>										Run
wf run <workfile> --nodes node1       							Run specific nodes
wf run <workfile> --wrapper 'docker run image bash -c "{}"'
wf server start
wf server start --foreground
wf server stop
wf server ls
wf edit add-node <file> "cmd" --x 100 --y 200 # prints the node ID
var=$(wf edit add-node <file> "cmd" --x 100 --y 200) # saves node ID to var
wf edit add-edge <file> <src> <tgt>
wf edit edit-status <file> node <id> "run"


gui
node and edge editor
double click node to edit contents
double click on empty portion of the canvas to add node
right click and drag on one node to another to draw edges between nodes
shift right click and drag to draw non-blocking edges
r to trigger node run
d to delete selected node(s)
w for wrapper
e to edit node
o to open from file

