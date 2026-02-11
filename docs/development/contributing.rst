Contributing
============

Dev setup
---------

Clone the repository and set up the development environment:

.. code-block:: console

   $ git clone <repo-url>
   $ cd sawmill
   $ source sourceme

The ``sourceme`` script creates a virtual environment in ``.venv/``
using ``uv`` and installs all dependencies (including dev extras). To
recreate the environment from scratch:

.. code-block:: console

   $ source sourceme --clean

Running tests
-------------

Run the full test suite:

.. code-block:: console

   $ pytest tests/ -v

Run a specific test file:

.. code-block:: console

   $ pytest tests/core/test_filter.py -v

Run with coverage:

.. code-block:: console

   $ pytest tests/ --cov=sawmill --cov-report=term-missing

Test file naming mirrors the source structure:
``sawmill/core/filter.py`` maps to ``tests/core/test_filter.py``.

Pre-commit hooks
----------------

The project uses `pre-commit <https://pre-commit.com/>`_ with hooks
configured in ``.pre-commit-config.yaml``:

- **Trailing whitespace** and **end-of-file** fixers
- **YAML/TOML** syntax validation
- **Debug statement** detection
- **Ruff** linting and formatting
- **mypy** type checking

Install hooks:

.. code-block:: console

   $ pre-commit install

Run manually:

.. code-block:: console

   $ pre-commit run --all-files

Docker dev loop
---------------

The ``ralph-loop.sh`` script runs Claude Code in a Docker container for
autonomous development iterations:

.. code-block:: console

   $ ./ralph-loop.sh --iterations 3
   $ ./ralph-loop.sh --continuous

Options:

``--iterations N``
   Run N iterations (default: 1).

``--continuous``
   Run until all tasks complete or an error occurs.

``--dry-run``
   Show what would be done without executing.

``--no-docker``
   Run directly on the host instead of in a container.

``--interactive``
   Drop into an interactive shell after each iteration.

The ``Dockerfile`` builds a container with Python 3.11, Node.js, and
Claude Code CLI pre-installed.

Building docs
-------------

Install documentation dependencies and build:

.. code-block:: console

   $ pip install -r docs/requirements.txt
   $ cd docs && make html

The built documentation is in ``docs/_build/html/``. Open
``docs/_build/html/index.html`` in a browser to review.
