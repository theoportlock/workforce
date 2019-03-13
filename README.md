# Pattern Recognition

This is a project designed to find patterns in a bitarray datastream. 

## Pipeline summary

1. Reading the "input.txt" file and convert each letter to a binary represenation of their ascii character
2. Drip feed each bit into a temporary array 
3. Increase the sparcity by changing the base of the temporary array
4. Measure distances between active nodes in the temporary array and output into a distances array
5. Find all combinations of active nodes in the distances array and output into combinations array. Each active combination element will represent a feature of the original input

## Program summary

*  inreader - opens file and returns a bitarray of contents
* addnewelement - Removes the rightmost element of an array, shuffles the information down towards that empty space and adds a new input node	
* binadder - Removes the rightmost element of an array, shuffles the information down towards that empty space and adds a new input node
* basechanger - converts bitarray into a single binary representing the full array's value
* comb2 - returns a bitarray of all combinations of an input bitarray. Puts an incorrect empty bit at start of bitarray - to fix
* packer - returns decimal array of active nodes counting from the left
* splitter - returns bitarray of distances between active nodes in an array of total distance possibilities. This removes the effects of array transpositions and inversions
* tis - main file

## To do:
- Fix combinations
- Play around with node delay mechanics for pattern memory
- Create and link nodes that do an action when a pattern is recognised
- Real time reader and writer
- Investigate different inputs (picture files e.t.c.)

I'm pretty new to all this, any suggestions more than welcome! 
