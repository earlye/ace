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
def main(argv):    
    builder = Builder(argv)
    builder.run()
    
if __name__ == "__main__":
    main(sys.argv[1:])
