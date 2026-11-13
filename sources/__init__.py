"""
THE LIST OF AVAILABLE SOURCES
=============================
Each source is one file in this folder with a fetch(settings) function.

To add a new source (for example a job board):
    1. Create a new file here, e.g. job_board.py, with a fetch(settings)
       function that returns rows with the standard columns.
    2. Add one line to SOURCES below.
    3. Put its name under source -> type in settings.yaml.
Nothing else in the pipeline needs to change.
"""

from sources import openfda_recalls

# Left side = the name used in settings.yaml. Right side = the function to run.
SOURCES = {
    "openfda_recalls": openfda_recalls.fetch,
}
