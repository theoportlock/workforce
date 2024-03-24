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


Run bash commands with python multiprocessing according to a csv file edgelist.

* Free software: MIT license
* Documentation: https://workforce.readthedocs.io.


Installation
------------
Installation can be done with 

.. code-block:: bash

   pip install workforce

Building a workforce workflow
-----------------------------
To build a workflow, simply run:

.. code-block:: bash

   workforce

Then, paste the IP address into into your browsers address bar and build your program.

Running workforce
-----------------
To run a sample plan from workforce github project:

.. code-block:: bash

   workforce example_plan.csv

To import and use in a python shell, use the following command:

.. code-block:: python

   from workforce.workforce import worker
   steve = worker("<PLAN.CSV>")
   steve.run()

The schema should be in the format of a csv with two columns. On the left and right column is the source and target command respectively (see example). Produces a logfile for each run.
