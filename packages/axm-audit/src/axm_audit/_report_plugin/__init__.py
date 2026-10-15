"""Directory holding the pytest reporting plugin injected into target runs.

Nothing here is imported by ``axm_audit``: :mod:`axm_audit.core.pytest_env`
puts this directory on the ``PYTHONPATH`` of the pytest subprocess and loads
``axm_audit_report_plugin`` into it with ``-p``. The directory contains that one
module only, so exposing it on a target's path shadows nothing.
"""
