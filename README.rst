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

+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
| Prefix                            | Suffix                | Description                                                                     |
+===================================+=======================+=================================================================================+
| ``tmux send-keys``                | ``C-m``               | Sends each command to a tmux session and executes it.                           |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
| ``ssh ADDRESS``                   |                       | Executes each command remotely on the specified server.                         |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
| ``parallel``                      | ``FILENAMES``         | Runs the pipeline on each specified filename.                                   |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
| ``docker run -it``                |                       | Executes each command within a Docker container with an interactive terminal.   |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
| ``echo``                          | ``>> commands.sh``    | Exports the pipeline commands to a bash script named ``commands.sh``.           |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
| ``conda activate ENV_NAME``       |                       | Activates a specified Conda environment before executing the commands.          |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
| ``nohup``                         |                       | Runs commands in the background.                                                |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
| ``sbatch``                        |                       | Submits commands to Slurm-managed servers.                                      |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
| ``kubectl run``                   |                       | Executes commands on a Kubernetes cluster.                                      |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
| ``sudo``                          |                       | Executes commands with elevated privileges.                                     |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
| ``env VAR1=value1 VAR2=value2``   |                       | Sets environment variables for the command.                                     |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
| ``nice -n 10``                    |                       | Adjusts the process priority.                                                   |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
| ``/usr/bin/time -v``              |                       | Times command execution with resource statistics.                               |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
| ``setsid``                        |                       | Launches commands in a new session.                                             |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
| ``strace -o trace.log``           |                       | Traces system calls for debugging.                                              |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
|                                   | ``>> logfile 2>&1``   | Appends output to log file.                                                     |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
|                                   | ``| tee output.log``  | Shows output in terminal and saves to file.                                     |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+
| ``powershell.exe``                |                       | Executes commands in Windows PowerShell.                                        |
+-----------------------------------+-----------------------+---------------------------------------------------------------------------------+

To run individual process(es) from the editor, select the process(es) in the order that you wish them to be excecuted and click the 'Run' button. The command line from where the builder was launched will display the standard output and error for each process.

Deleting processes or edges on the project can be done by selecting a process and clicking the 'Delete' button

The simplest way to edit a process is to click the edge that the process is connected to. This will fill the 'Input' box with the connection details. You can then add a new node with those connections and delete the old process.

This is tested on mac and linux but work requires work for windows integration except for wsl2
