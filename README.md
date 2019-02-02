Pattern Recognition

Program summary

addnewelement
Removes the rightmost element of an array, shuffles the information down towards that empty space and adds a new input node	

binadder
Removes the rightmost element of an array, shuffles the information down towards that empty space and adds a new input node

binminuser
opposite of binadder - not started yet

basechanger1
converts bitarray into a single decimal representing the full array's value

basechanger
converts bitarray into a single binary representing the full array's value

comb1
old attempt to find combinations in group, rather than binary, order

comb2
finds combinations but puts an incorrect empty bit at start of bitarray - to fix

comb
finds combinations and outputs decimals of active combinations

entropy
works like combinations finder but finds all possible correlations

inreader
opens file and returns a bitarray of contents

packer
returns decimal array of active nodes counting from the left

unpacker
returns bitarray of active nodes in a decimal array

splitter
returns bitarray of distances between active nodes in an array of total distance possibilities

tis
main file
.....


Pipeline summary

1. Reading the "input.txt" file
2. Convert each letter to a binary represenation of their ascii character
3. Drip feed each bit into an array 
4. Increase the sparcity of the array
5. Measure distances between active nodes in the array and output into a distances array
6. Find all combinations of active nodes in the distances array and output into combinations array
7. Find all groups of active nodes in the combinations array and output into grouping array

To do:
- fix combinations
- add bit differences function (xor gates)
- incorporate charge delay function to increase time resolution
- fix sparcity amount problem (solution may lie above)
- investigate the node delay mechanics
- make real time reader
- create and link action nodes
- image import (live and from webcam perhaps)
- output a script writer for a variety of outputs (bash compatibility, drone flight, image generation etc.)
- need to control node size - 2^8 = 256. sigma 256 is all combinations of just 2 letters is 32896... (like counting in base 256 with no 0s)
