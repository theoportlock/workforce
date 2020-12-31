# workforce
A tool for running bash commands with python multiprocessing according to a csv file edgelist. There are no requirements for the default program that are outside the Python Standard Library.

To try a sample plan, run with:
`python workforce.py plan.csv`

To view the program graph, networkx and matplotlib are required. The -g flag is required to plot:
`python3 workforce.py -g plan.csv`
![Graph](example_instructions.csv.png)

The schema should be in the format of a csv with two columns. On the left and right column is the source and target command respectively (see example). Produces a logfile for each run. The following bashrc alias is recommended if this repository is in your home directory:
`alias wf="python ~/workforce/workforce.py"`

Testing can be done within this directory by running:
`python -m unittest -v`
