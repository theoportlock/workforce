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

.. image:: docs/images/small.png
    :alt: Small pipeline example
    :align: center
    :width: 800px

.. image:: docs/images/complex.png
    :alt: Complex pipeline editor view
    :align: center
    :width: 800px

Build and run a pipeline of bash commands with python multiprocessing according to a graphml file.

* Free software: MIT license
* Documentation: https://workforce-documentation.readthedocs.io.

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

or:

.. code-block:: bash

   python -m workforce

To open a previously constructed pipeline, run:

.. code-block:: bash

   wf <PIPELINE.graphml>
    
If a `Workfile` is in the current directory:

.. code-block:: bash

   wf

Running workforce plan
----------------------
To run a sample plan from workforce github project from the GUI, click run_all or shift r. Run from cli with:

.. code-block:: bash

   wf run Workfile

Prefix and Suffix
-----------------
Adding the following prefix and suffixes to the wf run command (or within gui) will add those prefix and suffixes to each command ran by the pipeline.

+-------------------------------+---------------------------------------------------------------------------------+
| Options                       | Description                                                                     |
+===============================+=================================================================================+
| -p "tmux send-keys" -s "C-m"  | Sends each command to a tmux session and executes it.                           |
+-------------------------------+---------------------------------------------------------------------------------+
| -p "ssh ADDRESS"              | Executes each command remotely on the specified server.                         |
+-------------------------------+---------------------------------------------------------------------------------+
| -p "parallel" -s "FILENAMES"  | Runs the pipeline on each specified filename.                                   |
+-------------------------------+---------------------------------------------------------------------------------+
| -p "docker run -it"           | Executes each command within a Docker container with an interactive terminal.   |
+-------------------------------+---------------------------------------------------------------------------------+
| -p "echo" -s ">> commands.sh" | Exports the pipeline commands to a bash script named ``commands.sh``.           |
+-------------------------------+---------------------------------------------------------------------------------+
| -p "conda activate ENV_NAME"  | Activates a specified Conda environment before executing the commands.          |
+-------------------------------+---------------------------------------------------------------------------------+
| -p "nohup"                    | Runs commands in the background.                                                |
+-------------------------------+---------------------------------------------------------------------------------+
| -p "sbatch"                   | Submits commands to Slurm-managed servers.                                      |
+-------------------------------+---------------------------------------------------------------------------------+
| -p "kubectl run"              | Executes commands on a Kubernetes cluster.                                      |
+-------------------------------+---------------------------------------------------------------------------------+
| -p "sudo"                     | Executes commands with elevated privileges.                                     |
+-------------------------------+---------------------------------------------------------------------------------+
| -p "env VAR1=value1"          | Sets environment variables for the command.                                     |
+-------------------------------+---------------------------------------------------------------------------------+
| -p "nice -n 10"               | Adjusts the process priority.                                                   |
+-------------------------------+---------------------------------------------------------------------------------+
| -p "/usr/bin/time -v"         | Times command execution with resource statistics.                               |
+-------------------------------+---------------------------------------------------------------------------------+
| -p "setsid"                   | Launches commands in a new session.                                             |
+-------------------------------+---------------------------------------------------------------------------------+
| -p "strace -o trace.log"      | Traces system calls for debugging.                                              |
+-------------------------------+---------------------------------------------------------------------------------+
| -s ">> logfile 2>&1"          | Appends output to log file.                                                     |
+-------------------------------+---------------------------------------------------------------------------------+
| -s "| tee output.log"         | Shows output in terminal and saves to file.                                     |
+-------------------------------+---------------------------------------------------------------------------------+
| -p "powershell.exe"           | Executes commands in Windows PowerShell.                                        |
+-------------------------------+---------------------------------------------------------------------------------+

To run individual process(es) from the editor, select the process(es) in the order that you wish them to be excecuted and click the 'Run' button (or shortcut with r key). Opening the terminal with shortcut t (or on the toolbar), you can see the output of the commands

This is tested on mac, linux, and windows powershell and wsl2.
