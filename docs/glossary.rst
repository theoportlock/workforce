.. _glossary:

========
Glossary
========

This glossary defines key terms and concepts used in Workforce.

.. _blocking-edge:

Blocking Edge
~~~~~~~~~~~~~

A **blocking edge** is the default edge type in Workforce that represents a hard dependency between two nodes. When a node has blocking edges as inputs, it will only transition to the ``run`` state after **all** incoming blocking edges are marked as ``to_run``. This enforces strict sequential execution and prevents a node from starting until all its blocking dependencies have completed.

Blocking edges are used for:

* Enforcing strict execution order (DAG-like workflows)
* Ensuring all prerequisites are complete before proceeding
* Preventing race conditions in dependent operations

See also: :ref:`dependency-resolution`, :ref:`edge-type`, :ref:`non-blocking-edge`

.. _non-blocking-edge:

Non-Blocking Edge
~~~~~~~~~~~~~~~~~

A **non-blocking edge** is an optional edge type that represents a soft dependency or trigger relationship between two nodes. When a non-blocking edge becomes ``to_run``, the target node is immediately set to ``run`` state without waiting for other incoming edges. This allows nodes to execute (or re-execute) based on a single upstream trigger.

Non-blocking edges enable:

* Multiple executions of a node (re-triggering)
* Fan-out patterns where multiple nodes trigger independent branches
* Workflows that don't conform to strict DAG structure
* Immediate propagation without waiting for all dependencies

See also: :ref:`re-triggering`, :ref:`edge-type`, :ref:`blocking-edge`

.. _re-triggering:

Re-Triggering
~~~~~~~~~~~~~~

**Re-triggering** is the behavior where a node executes multiple times during a single workflow run, each time triggered by a non-blocking edge from a predecessor. Unlike blocking edges which permit only one execution per run, non-blocking predecessors can cause a node to run again without clearing other dependencies.

Key characteristics:

* Each trigger from a non-blocking edge sets the target to ``run`` state
* The node executes and its log is overwritten with new output
* Multiple execution paths through the workflow are possible
* Strictly bounded by subset run boundaries

See also: :ref:`non-blocking-edge`, :ref:`dependency-resolution`

.. _edge-type:

Edge Type
~~~~~~~~~

An **edge type** is an attribute of edges in a Workforce workflow that determines how the edge affects dependency resolution and node execution. Workforce supports two edge types:

* **blocking** (default) - Enforces strict dependency; target waits for all blocking inputs
* **non-blocking** - Soft trigger; immediately runs target without waiting for other inputs

Edge types are:

* Stored as the ``edge_type`` attribute in GraphML workflow files
* Visible in the GUI with visual distinction (solid vs dashed lines)
* Controllable via REST API, CLI, and GUI keyboard modifiers
* Backward compatible (existing workflows default to all blocking edges)

See also: :ref:`blocking-edge`, :ref:`non-blocking-edge`

.. _subset-run:

Subset Run
~~~~~~~~~~

A **subset run** is a workflow execution that operates on a selected subset of nodes rather than the entire graph. This is the unified execution model used internally by Workforce for all runs.

Characteristics:

* Can be explicitly selected (GUI/CLI: select specific nodes to run)
* Can be implicit (default: run all root nodes or failed nodes)
* Induces a subgraph of only those nodes and their connecting edges
* Propagation is strictly confined within the subgraph boundaries
* Edges leading outside the subset are ignored
* Prevents execution from "bleeding" beyond the intended scope

The unified subset model ensures:

* Consistent behavior whether running full pipeline or specific nodes
* Safe resumption of failed nodes without affecting unrelated parts
* Clean termination once the selected subgraph is exhausted

See also: :ref:`dependency-resolution`, :ref:`cycle-detection`

.. _cycle-detection:

Cycle Detection
~~~~~~~~~~~~~~~

**Cycle detection** is the process of identifying and preventing directed cycles in a workflow that would cause infinite execution loops. Workforce performs cycle detection on the :ref:`blocking-edge` subgraph only.

Key points:

* Only **blocking edges** are considered for cycle detection
* Non-blocking edges are ignored when checking for cycles
* This allows workflows with non-blocking cycles (safe, no infinite loops)
* Cycles in blocking edges are detected before execution begins
* Prevents deadlocks and infinite loops in workflows

Cycle detection ensures:

* DAG structure for blocking dependencies (acyclic graph)
* Deterministic execution order for dependent operations
* Early error reporting if cycles exist in blocking edges

See also: :ref:`blocking-edge`, :ref:`non-blocking-edge`, :ref:`dependency-resolution`

.. _dependency-resolution:

Dependency Resolution
~~~~~~~~~~~~~~~~~~~~~

**Dependency resolution** is the scheduler process that determines which nodes are ready to execute based on their incoming edge statuses and types. The process respects both :ref:`blocking-edge` and :ref:`non-blocking-edge` semantics.

Resolution steps:

1. A node completes execution (transitions to ``ran`` status)
2. All outgoing edges from that node are marked as ``to_run``
3. **For blocking edges**: Target node checks if **all** incoming blocking edges are ``to_run``
   
   * If yes: Target transitions to ``run`` state
   * If no: Target remains waiting
   
4. **For non-blocking edges**: Target immediately transitions to ``run`` state
   
   * No need to wait for other incoming edges
   * Allows multiple executions during a single run
   
5. Targets within :ref:`subset-run` boundaries execute; targets outside the subset are ignored

This mechanism ensures:

* Nodes execute only when dependencies are satisfied
* Blocking edges enforce prerequisite order
* Non-blocking edges provide flexible triggering
* Subset boundaries prevent unwanted execution

See also: :ref:`blocking-edge`, :ref:`non-blocking-edge`, :ref:`cycle-detection`
