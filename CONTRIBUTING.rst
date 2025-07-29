Contributing
============

Thanks for your interest in contributing to **workforce**!

This document outlines how you can help improve the project — whether through bug reports, code contributions, documentation, or ideas.

Getting Started
---------------

1. Fork the repository on GitHub.
2. Clone your fork to your local machine:

   .. code-block:: bash

      git clone https://github.com/your-username/workforce.git
      cd workforce

3. Create a new virtual environment and activate it:

   .. code-block:: bash

      python3 -m venv venv
      source venv/bin/activate

4. Install the package in editable mode with development dependencies:

   .. code-block:: bash

      pip install -e .[dev]

   If you don’t have `[dev]` extras set up yet, install manually:

   .. code-block:: bash

      pip install -r requirements.txt
      pip install -r requirements-dev.txt  # optional

Reporting Issues
----------------

If you encounter a bug or have a feature request:

- Search the existing [issues](https://github.com/theoportlock/workforce/issues)
- If it doesn’t exist, create a new issue and provide:
  - A minimal reproducible example (if applicable)
  - Error message or traceback
  - Operating system and Python version

Making Changes
--------------

- Follow PEP8 via `flake8` or `ruff`.
- Add or update tests for new functionality.
- Document new features clearly in `README.rst` or appropriate docs.
- Use clear commit messages.
- Test your changes locally.

Running Tests
-------------

This project uses `pytest`. To run tests:

.. code-block:: bash

   pytest

To run tests with coverage:

.. code-block:: bash

   pytest --cov=workforce

Documentation
-------------

Documentation lives in the `docs/` folder and uses Sphinx. To build locally:

.. code-block:: bash

   cd docs
   make html

Open `_build/html/index.html` in your browser to preview.

Submitting a Pull Request
-------------------------

Once you’ve tested your changes:

1. Push to your fork:

   .. code-block:: bash

      git push origin your-branch-name

2. Open a pull request on GitHub.
3. Reference the issue being addressed (if any).
4. Explain what your changes do and why they’re needed.

Code of Conduct
---------------

Be respectful and constructive. We're building a community that encourages curiosity, collaboration, and learning.


