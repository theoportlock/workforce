# workforce
A tool for running commands with multiprocessing according to a csv file schema. There are no requirements for the program that are outside the Python Standard Library.

To try a sample plan, run with:
`python3 workforce.py plan.csv`

Other "Manager" scripts can be ran from the csv file that plot a graph of the csv program structure:
![Graph](example_instructions.csv.png)

The schema should be in the format of a csv with two columns. On the left and right column is the source and target command respectively (see example). Produces a logfile for each run. The following alias can be made to the bashrc if the git repository is in your home directory:
`alias wf="~/workforce/workforce.py"`

Testing can be done with:
`python3 -m unittest -v`
