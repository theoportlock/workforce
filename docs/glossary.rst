.. _glossary:

========
Glossary
========

Workfile
~~~~~~~~

A GraphML file containing a Workforce graph.

Worksession
~~~~~~~~~~~

A workfile loaded into the Workforce server. A worksession is the target of CLI
and web-editor operations.

.. _blocking-edge:

Blocking edge
~~~~~~~~~~~~~

The default edge type. Its target cannot execute until every incoming blocking
edge in the active run subgraph is ``ready``.

.. _non-blocking-edge:

Non-blocking edge
~~~~~~~~~~~~~~~~~

An edge that does not add a prerequisite to its target. It may trigger the
target when it becomes ready, enabling event-like fan-out, re-execution, and
loops.

.. _subset-run:

Subset run
~~~~~~~~~~

A run restricted to an induced subgraph selected by CLI or web-editor nodes.
Only its nodes may change state and only its internal edges propagate readiness.
Edges crossing its boundary have no execution effect.

Ready edge
~~~~~~~~~~

An edge marked ``ready`` because its source completed successfully. Once all
incoming blocking edges for a target are ready, those flags are cleared and the
target is scheduled.

Node status
~~~~~~~~~~~

Nodes normally move through ``""`` → ``run`` → ``running`` → ``ran``. A
running node that fails moves to ``fail``; a failed node may be moved back to
``run`` for another attempt.

Loop
~~~~

A directed cycle in a workflow. Workforce supports loops and does not impose a
DAG requirement. A loop may cause repeated execution, so its commands or graph
structure should provide an intended termination condition.
