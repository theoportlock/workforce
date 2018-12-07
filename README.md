Pattern Recognition

Main file
1. Defining how all combinations work
2. Reading the "input.txt" file
3. Make create specific amount of sparcity
4. Find all combinations of the string and activate specific nodes for each combination
5. Delay the signal decrease of these combinations 

To do:
- incorporate charge delay function to increase time resolution
- fix sparcity amount problem (solution may lie above)
- investigate the node delay mechanics
- make real time reader
- create and link action nodes
- image import (live and from webcam perhaps)
- output a script writer for a variety of outputs (bash compatibility, drone flight, image generation etc.)
- need to control node size - 2^8 = 256. sigma 256 is all combinations of just 2 letters is 32896... (like counting in base 256 with no 0s)

Split into parts:
basechanger - adds sparcity
comb - data extract
distancesplitter - removes time dimension
  input text
  create an empty nerv of any size (tbd)
  create nodes that look at distances between nerv cells that sould be one less than nerv
  for each letter in the input text
  shuffle the nerv cells to prepare for the new binary
  add new binary from input text
  gap incrimentation increase starting at 1
  reset current gap incrimentation to be 0
  search nerv for a gap matching the current size
  if found then
  activate the corresponding node
lagger - allows for memory



