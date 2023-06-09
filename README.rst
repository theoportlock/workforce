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

.. code:: bash

        pip install workforce

Running workforce
-----------------
To try a sample plan, run with:

.. code:: bash

        workforce example_plan.csv

To view the program graph, networkx and matplotlib are required. The -g flag is required to produce a dot file of the network:

.. code:: bash

        workforce -g example_plan.csv

To import and use in a python shell, use the following command:

.. code:: python3
        from workforce.workforce import worker
        steve = worker("<PLAN.CSV>")
        steve.run()

Graph print
-----------
Converting the graph to a dot can be done using an online dot viewer or using Graphviz software with the example command:

.. code-block:: bash

        dot -Tpng -Kdot -o <DOT_FILENAME>.png <DOT_FILENAME>

.. image:: example_plan.png

The schema should be in the format of a csv with two columns. On the left and right column is the source and target command respectively (see example). Produces a logfile for each run.

Testing
-------
Testing can be done within this directory by running:

.. code-block:: bash

        python -m unittest -v
