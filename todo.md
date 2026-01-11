Remote wf server ls that accepts arg for server name

wf edit = ERROR
wf edit node status 'ran' = uses wf server
wf edit edge 
wf edit merge?

wf server = if Workfile: wf server start Workfile else wf server start temp
wf server start = if Workfile: wf server start Workfile else wf server start temp
wf server stop = if Workfile: wf server stop Workfile else wf server stop temp
wf server list = list active servers
wf server list --watch = list active servers with watch

wf = if Workfile: if Workfile is a graphml: wf server Workfile; wf gui Workfile; wf server stop Workfile # Should there be an option to keep running and exit? maybe --bg?
wf gui = same as above
wf gui Workfile : same as above

wf run = if Workfile: if Workfile is a graphml: wf server Workfile; wf run Workfile; wf server stop Workfile
wf run Workfile = if Workfile is a graphml: wf run Workfile
wf run --bg Workfile = if Workfile is a graphml: wf run Workfile in background # do i want to specify the port anywhere?
wf run node Workfile --id 1124  = uses wf edit to edit file
wf run nodes Workfile --ids 1124,3423,235235  = run according to the order of the pipeline

wf pull/push?
wf clone?
wf status?
wf --version -v?
wf browser?

home server that manages the registry in memory - potential webviewer
wf runner stop run_id - figure out
A way to save the wf request log for modification, execution
Loading and saving wrappers as a dropdown menu of options that can be added to
Minimap for the bottom left
Edges need to change color based on to_run
Save PDF of layout button
Some way to quickly open file in node (using default program)
zoom should be from the center of current canvas view
Shortcuts on all the buttons plus in help menu
design to disown on run 
Sort out the filelock for the gui
Fix initialization so that if there are edges that are 'to_run' then don't start from indegree=0
click and drag into canvas - wont work for wsl2 sadly but update anyway
bash updater button in node editos
shortcuts for mac, win and lin - i3 button press combination and windows shortcut
Connect shell button or keep separate?
output of command should be saved to the pipeline itself as a run log - can use tee also
Logging for dropdown on nodes (output of script + errors possibly separate)
undo-redo? use git? - need to be carefull of this
pipeline diffs/shapshots/copy nodes
Keep nodes that have ran to ran (olin suggestion)
prefix suffix dropdowns and potential config files for running.
function builder with copy command to clipboard option?
Do I use the CLI to save and load nodes (fully operational from cli)
Update the prefix suffix suggestions
    Prefix bash -c 'tmux send-keys " Suffix " C-m'
FLASK socketIO SERVER - need to make an enter and exit function that is called by the gui and the run commands
