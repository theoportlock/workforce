=========
workforce
=========


.. image:: https://img.shields.io/pypi/v/workforce.svg
        :target: https://pypi.python.org/pypi/workforce

.. image:: https://img.shields.io/travis/theoportlock/workforce.svg
        :target: https://travis-ci.com/theoportlock/workforce

.. image:: https://readthedocs.org/projects/workforce/badge/?version=latest
        :target: https://workforce.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status


Build and run a pipeline of bash commands with python multiprocessing according to a tsv file edgelist.

* Free software: MIT license
* Documentation: https://workforce.readthedocs.io.


Installation
------------
Installation can be done with:

.. code-block:: bash

   pip install workforce

Building a workforce workflow
-----------------------------
To launch the pipeline editor, run:

.. code-block:: bash

   wf

To open a previously constructed pipeline, run:

.. code-block:: bash

   wf <PIPELINE.graphml>

Running workforce plan
----------------------
To run a sample plan from workforce github project:

.. code-block:: bash

   wf run example_plan.graphml

Live viewing workforce plan
---------------------------
To view a plan as it is excecuting:

.. code-block:: bash

   wf view example_plan.graphml

Prefix and Suffix
-----------------
Adding the following prefix and suffixes to the wf run command will add those prefix and suffixes to each command ran by the pipeline.

prefix tmux send-keys, suffix C-m will send each command to tmux and run in same session
prefix ssh ADDRESS will run each command on a server
prefix parallel, suffix FILENAMES will run the pipeline on each filename
prefix docker run -it will run each command with the same environment
prefix echo, suffix >> commands.sh will export the pipeline to a bash script
prefix conda activate ENV_NAME will activate conda envionment before running
prefix nohup Runs the command in the background and disowns it, preventing the command from being stopped even if the terminal is closed.
prefix sbatch for running on slurm servers
prefix kubectl run for running on kubernetes servers
prefix sudo for enhanced privelages
prefix "env VAR1=value1 VAR2=value2" to set environmental variables before running
prefix "nice -n 10" to be nice
prefix "/usr/bin/time -v" for time excecution and resource usage
prefix setsid to launch each command in a new session, decoupling it from the current terminal.
prefix "strace -o trace.log" to trace system calls and signals for debugging, with output logged to a file.
suffix ">> logfile 2>&1" to append both standard output and error to a log file for persistent logging.
suffix "| tee output.log" to pipe command output to both the terminal and a file simultaneously.

To run individual process(es) from the editor, select the process(es) in the order that you wish them to be excecuted and click the 'Run' button. The command line from where the builder was launched will display the standard output and error for each process.

Deleting processes or edges on the project can be done by selecting a process and clicking the 'Delete' button

The simplest way to edit a process is to click the edge that the process is connected to. This will fill the 'Input' box with the connection details. You can then add a new node with those connections and delete the old process.

This is tested on mac and linux but work requires work for windows integration except for wsl2
