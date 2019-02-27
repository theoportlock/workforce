#Pattern Recognition
This is a project designed to find patterns in a bitarray datastream. 

##Pipeline summary

1. Reading the "input.txt" file and convert each letter to a binary represenation of their ascii character
2. Drip feed each bit into a temporary array 
3. Increase the sparcity of the array by changing its base
4. Measure distances between active nodes in the array and output into a distances array
5. Find all combinations of active nodes in the distances array and output into combinations array
6. Find all groups of active nodes in the combinations array and output into grouping array

##Program summary

inreader
opens file and returns a bitarray of contents

addnewelement
Removes the rightmost element of an array, shuffles the information down towards that empty space and adds a new input node	

binadder
Removes the rightmost element of an array, shuffles the information down towards that empty space and adds a new input node

basechanger
converts bitarray into a single binary representing the full array's value

comb2
returns a bitarray of all combinations of an input bitarray. Puts an incorrect empty bit at start of bitarray - to fix

comb
same as comb2 but broken

entropy
works like combinations finder but finds all pairs of active nodes

packer
returns decimal array of active nodes counting from the left

unpacker
returns bitarray of active nodes in a decimal array

splitter
returns bitarray of distances between active nodes in an array of total distance possibilities

tis
main file

##To do:
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
