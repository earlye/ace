#!/usr/bin/python
import datetime
import glob
import json
import os
import shutil
import string
import subprocess
import sys
import time

from builder import Builder
from run_cmd import run_cmd
from pprint import pprint

# Parse arguments and begin the build.
def main():
    try:
        builder = Builder(sys.argv[1:])
        builder.run()
    except:
        return 1

if __name__ == "__main__":
    sys.exit( main() )
