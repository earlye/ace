from __future__ import print_function

import platform
import string
import subprocess
import sys

class RunCmdResult(object):
    def __init__(self):
        self.retCode = 0;
        self.stdout = [];
        self.stderr = [];
    def addStdOut(self,lines,echo=True):
        if (len(lines)==0):
            return;
        lines = map(lambda line: line.rstrip('\n'),lines)
        if (echo):
            print("\n".join(lines), file=sys.stdout)
        self.stdout.extend(lines)
    def addStdErr(self,lines,echo=True):
        if (len(lines)==0):
            return;
        lines = map(lambda line: line.rstrip('\n'),lines)
        if (echo):
            print("\n".join(lines), file=sys.stderr)
        self.stderr.extend(lines)

def run_cmd(args,throwOnNonZero = True):
    print(' '.join(args))
    # set the use show window flag, might make conditional on being in Windows:
    if platform.system() == 'Windows':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    else:
        startupinfo = None
    # pass as the startupinfo keyword argument:
    p=subprocess.Popen(args,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             stdin=subprocess.PIPE,
                             startupinfo=startupinfo)

    result = RunCmdResult();
    while(True):
        result.retCode = p.poll()
        result.addStdOut(p.stdout.readlines(1024))
        result.addStdErr(p.stderr.readlines(1024))
        if (result.retCode is not None):
            # Append any additional lines
            result.addStdOut(p.stdout.readlines())
            result.addStdErr(p.stderr.readlines())
            break;

    if (throwOnNonZero and result.retCode != 0):
        raise Exception("Command Exited with status=%d" %result.retCode)
    return result;
