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

   wf_edit

To open a previously constructed pipeline, run:

.. code-block:: bash

   wf_edit <PIPELINE.graphml>

Running workforce plan
----------------------
To run a sample plan from workforce github project:

.. code-block:: bash

   wf_run example_plan.graphml

Live viewing workforce plan
---------------------------
To view a plan as it is excecuting:

.. code-block:: bash

   wf_run example_plan.graphml

To run individual process(es) from the editor, select the process(es) in the order that you wish them to be excecuted and click the 'Run' button. The command line from where the builder was launched will display the standard output and error for each process.

Deleting processes from the project can be done by selecting a process and clicking the 'Delete' button

The simplest way to edit a process is to click the edge that the process is connected to. This will fill the 'Input' box with the connection details. You can then add a new node with those connections and delete the old process.

To import and use in a python shell, use the following command:

.. code-block:: python

   from workforce.run import run_tasks
   from workforce.view import plot_network
   from workforce.edit import gui
   run_tasks("<PLAN.GRAPHML>")
   plot_network("<PLAN.GRAPHML>")
   gui("<PLAN.GRAPHML>")


This is tested on mac and linux but work requires work for windows integration except for wsl2
