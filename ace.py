#!/usr/bin/python
import argparse
import glob
import json
import os
import subprocess
import sys
import time

from pprint import pprint

# Parse arguments and begin the build.
def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('-d','--dir',dest='build_dir',default='.',help='directory to build in.');
    parser.add_argument('-r','--rebuild',dest='rebuild',action='store_true',default=False,help='Rebuild everything.');
    args = vars(parser.parse_args(argv))
    descend(args,args['build_dir']);    

# Build in the current directory based on ace.json
def build_ace(args):
    print "-- Building with ACE"
    ace = json.load(open("ace.json"))
    pprint(ace)
    {
        'program': build_ace_program(ace,args)
    }.get(ace['type'])

# Build ace program
def build_ace_program(ace,args):
    print "-- Building program with ACE"
    source_modules=[]
    object_modules=[]
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".cpp") or file.endswith(".cxx") :
                source_modules.append(os.path.join(root,file))
    pprint(source_modules)
    object_modules=[];
    for file in source_modules:
        object_modules.append(compile_module(ace,args,file))
    link(ace,args,object_modules)
    
# Build in the current directory, based on it being just a container of other projects
def build_container(args):
    print "-- Building as container"
    for root, dirs, files in os.walk("."):
        for dir in dirs:
            descend(args,dir)

# Build in the current directory
def build(args):
    if os.path.exists("ace.json"):
        return build_ace(args)
    if os.path.exists("Makefile"):
        return build_make(args);
    if os.path.exists("pom.xml"):
        return build_maven(args);
    return build_container(args);

# Descend into a directory and continue building there.
def descend(args,target_dir):
    if (target_dir=='.'):
        return build(args);        
    print "Entering directory `" + target_dir + "'"
    try:
        os.chdir(target_dir);
        build(args);
    finally:
        if not(target_dir == '.'):
            print "Leaving directory `" + target_dir + "'"

def replace_extension(filename,new_extension) :
    base_file, ext = os.path.splitext(filename)
    return base_file + new_extension

def read_dependency_file(filename):
    dependency_file = open(filename).readlines()
    result=[]
    for line in dependency_file:
        line = line.strip()
        colon = line.find(':')
        if colon >= 0:
            line = line[colon+1:].strip()
        if line.endswith('\\'):
            line = line[:-1].strip()
            #print line        
        result.append(line.strip())
    return result

def module_needs_compile(ace,args,path) :
    if args['rebuild'] :
        print "-- %s needs compile. -r specified." %path
        return True
    
    dependency_file = replace_extension(path,".d")
    if not os.path.isfile(dependency_file) :
        print "-- %s needs compile. No dependency information found" %path
        return True

    target_file = replace_extension(path,".o")
    if not os.path.isfile(target_file) :
        print "-- %s needs compile. Target does not exist" %path
        return True

    source_time = os.path.getmtime(path)
    dependency_time = os.path.getmtime(dependency_file)
    if source_time > dependency_time:
        print "-- %s needs compile. Source timestamp > Dependency timestamp" %path
        return True

    target_time = os.path.getmtime(target_file)
    if source_time > target_time:
        print "-- %s needs compile. Source timestamp > Target timestamp" %path
        return True

    dependencies = read_dependency_file(dependency_file)
    for dependency in dependencies:
        if not os.path.exists(dependency) :
            print "-- Module needs compile: \"%s\" does not exist" %dependency
            return True
        dependency_time = os.path.getmtime(dependency)
        if dependency_time > target_time:
            print "-- Module needs compile: %s newer than %s\n\t(%s vs %s)" %(dependency,target_file,dependency_time,target_time)
            return True
    
    return False

# Compile a single module
def compile_module(ace,args,path):
    target_file = replace_extension(path,".o")
    if not module_needs_compile(ace,args,path) :
        print "-- Skipping: " + path
        return target_file
    print "-- Compiling: " + path
    compiler_args=["g++"];
    compiler_args.append("-MD") # generate .d file
    compiler_args.append("-c") # compile, too!
    compiler_args.append("-o")
    compiler_args.append(target_file)
    compiler_args.append(path)
    pprint(compiler_args)
    subprocess.call(compiler_args)
    return target_file

# Link an ace program
def link(ace,args,objects):
    linker_args=["g++"];
    linker_args.append("-o")
    linker_args.append(ace['target'])
    for object in objects:
        linker_args.append(object)
    pprint(linker_args)
    subprocess.call(linker_args)
    
if __name__ == "__main__":
    main(sys.argv[1:])