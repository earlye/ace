#!/usr/bin/python
import argparse
import datetime
import glob
import json
import os
import shutil
import subprocess
import sys
import time

from ace_utils import *
from pprint import pprint

# Parse arguments and begin the build.
def main(argv):    
    parser = argparse.ArgumentParser()
    parser.add_argument('-d','--dir',dest='build_dir',default='.',help='directory to build in.');
    parser.add_argument('-r','--rebuild',dest='rebuild',action='store_true',default=False,help='Rebuild everything.');
    parser.add_argument('-nc','--no-clone-missing',dest='clone-missing',action='store_false',default=True,help='Disable clone of missing repos when building containers.');
    pprint({"__file__":__file__,"realpath":os.path.realpath(__file__),"argv":argv})
    args = vars(parser.parse_args(argv))
    descend(args,args['build_dir']);    
    
# Build in the current directory based on ace.json
def build_ace(args):
    ace = json.load(open("ace.json"))
    if not 'include_dirs' in ace:
        ace['include_dirs'] = [];
    ace['need_link'] = False;
        
    if os.path.isdir("include") :
        ace['include_dirs'].append("include")
        
    print "-- Building \"%s\" with ACE" %ace['type']
    if ace['type'] == 'program' :
        build_ace_program(ace,args)
    elif ace['type'] == 'library' :
        build_ace_library(ace,args)
    elif ace['type'] == 'container' :
        build_ace_container(args,ace)
    else:
        print "unrecognized type"

    
# Build ace program
def build_ace_program(ace,args):
    print "-- Building program with ACE"
    source_modules=[]    
    source_objects=[]
    test_modules=[]
    test_objects=[]
    test_methods=[]
    if 'dependencies' in ace :
        for dependency in ace['dependencies']:
            path = "~/.ace/%s/include" %dependency['name']
            path = os.path.expanduser(path)
            ace['include_dirs'].append(path)
    for root, dirs, files in os.walk("src/main"):
        for file in files:
            if file.endswith(".cpp") or file.endswith(".cxx") :
                source_modules.append(os.path.join(root,file))
    for root, dirs, files in os.walk("src/test"):
        for file in files:
            if file.endswith(".cpp") or file.endswith(".cxx") or file.endswith(".C"):
                test_modules.append(os.path.join(root,file))
    pprint({"source_modules":source_modules,"test_modules":test_modules})
    source_objects=[];
    for file in source_modules:
        source_objects.append(compile_module(ace,args,file))
    if not os.path.exists(ace['target']):
        ace['need_link'] = True
    if ace['need_link'] :
        link(ace,args,source_objects)

    # Build test modules...
    for file in test_modules:
        test_objects.append(compile_module(ace,args,file))
    for object in test_objects:
        scan_object_for_tests(args,object,test_methods);

    nomain_source_objects = filter(nomain,source_objects)
                                    
    test_objects.append(generate_test_harness(ace,args,test_methods));
    link_test_harness(ace,args,nomain_source_objects,test_objects)
    run_cmd(["./.test_harness.exe"]);
        
# Build an ace library
def build_ace_library(ace,args):
    print "-- Building library with ACE"
    source_modules=[]
    source_objects=[]
    test_modules=[]
    test_objects=[]
    test_methods=[]
    for root, dirs, files in os.walk("src/main"):
        for file in files:
            if file.endswith(".cpp") or file.endswith(".cxx") or file.endswith(".C"):
                source_modules.append(os.path.join(root,file))
    for root, dirs, files in os.walk("src/test"):
        for file in files:
            if file.endswith(".cpp") or file.endswith(".cxx") or file.endswith(".C"):
                test_modules.append(os.path.join(root,file))
    pprint({"source_modules":source_modules,"test_modules":test_modules})

    # Build source modules...
    source_objects=[];
    for file in source_modules:
        source_objects.append(compile_module(ace,args,file))
        
    if not os.path.exists("%s.a" %ace['target']):
        ace['need_link'] = True

    if ace['need_link'] :
        archive(ace,args,source_objects)

    # Build test modules...
    for file in test_modules:
        test_objects.append(compile_module(ace,args,file))
    for object in test_objects:
        scan_object_for_tests(args,object,test_methods);

    test_objects.append(generate_test_harness(ace,args,test_methods));
    link_test_harness(ace,args,source_objects,test_objects)
    run_cmd(["./.test_harness.exe"]);
    

    # install the library in ~/.ace/
    path = "~/.ace/%s" %ace['name']
    path = os.path.expanduser(path)
    print "Installing library to %s" %path
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path)
    shutil.copytree("include" , "%s/include" %(path))
    shutil.copyfile("%s.a" %ace['target'], "%s/%s.a" %(path,ace['target']))
    json.dump(ace,open("%s/ace.json" %path,"w"))
    run_cmd(["find", path, "-type" , "f"])

def generate_test_harness(ace,args,test_methods) :
    variables = {};
    variables['automatically_generated'] = "Automatically generated by ACE @" + time.ctime();
    variables['test_declarations'] = [];
    variables['test_list'] = [];
    for test_method in test_methods:
        parts = filter(len,test_method.split(':'))
        basename = parts.pop()[:-len("()")] # remove () that is definitely there due to scan_objects_for_tests
        decl = "";
        name = "";
        for namespace in parts:
            decl += "namespace " + namespace + " {"
            name += namespace + "::";
        decl += "extern void " + basename + "();"
        name += basename;
        for namespace in parts:
            decl += "}"
        test_struct = "{ %s, \"%s\" }" %(name,name)
        variables['test_declarations'].append(decl)
        variables['test_list'].append(test_struct)

    variables['test_declarations']="\n".join(variables['test_declarations'])
    variables['test_list']=",\n".join(variables['test_list'])

    ace_dir=os.path.dirname(os.path.realpath(__file__))
    template_name=os.path.join(ace_dir,"cpp_test_template.cpp")
    template = string.Template(open(template_name).read())
    test_harness = template.substitute(variables)
    open(".test_harness.cpp","w").write(test_harness)
    return compile_module(ace,args,".test_harness.cpp")

def nomain(object) :
    functions = scan_object_for_functions(object)
    return "_main()" in functions

def scan_object_for_tests(args,object,test_methods):
    functions = scan_object_for_functions(object)
    for function in functions :
        if function.endswith("()") and (function.startswith("test") or "::test" in function):
            test_methods.append(function)

def scan_object_for_functions(object):
    ace_dir=os.path.dirname(os.path.realpath(__file__))
    method_lister=os.path.join(ace_dir,"method_list")
    args = [method_lister,object];
    result = run_cmd(args)
    return result.stdout
    
# Build in the current directory, based on it being just a container of other projects
def build_ace_container(args,ace):
    print "-- Building as ace container"
    if args['clone-missing'] and not ace == None and 'modules' in ace:
        print "-- checking for missing repos"
        for module in ace['modules']:
            if not os.path.isdir(module):
                moduleDefinition = ace['modules'][module];
                print "--- Need to clone module:" + module
                if "git-remotes" in  moduleDefinition:
                    if not "origin" in moduleDefinition["git-remotes"]:
                        raise Exception("Module \"" + module + "\" has git-remotes info, but no origin. Could not clone it.")
                    run_cmd(["git","clone",moduleDefinition["git-remotes"]["origin"],module]);
                else:
                    raise Exception("Module \"" + module + "\" has no repository info and is missing. Could not clone it.")
        
    for item in os.listdir("."):
        if not item.startswith('.') :
            if os.path.isdir(item) :
                descend(args,item)

def build_make(args):
    print "-- Building make project"
    make_args=["make"]
    run_cmd(make_args)

# Build in the current directory
def build(args):
    if os.path.exists("ace.json"):
        return build_ace(args)
    if os.path.exists("Makefile"):
        return build_make(args);
    if os.path.exists("pom.xml"):
        return build_maven(args);
    return build_ace_container(args,None);

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
            os.chdir("..")
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
        dependencies = line.split()
        for dependency in dependencies:
            result.append(dependency.strip())
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
    compiler_args.append("-std=c++14")
    compiler_args.append("-MD") # generate .d file
    compiler_args.append("-c") # compile, too!
    compiler_args.append("-o")
    compiler_args.append(target_file)
    for include_path in ace['include_dirs']:
        compiler_args.append("-I%s" %include_path);
    compiler_args.append(path)
    run_cmd(compiler_args)
    ace['need_link'] = True
    return target_file

def link_test_harness(ace,args,source_objects,test_objects):
    linker_args=["g++"]
    linker_args.extend(["-o",".test_harness.exe"]) #,".test_harness.o"])
    linker_args.extend(source_objects)
    linker_args.extend(test_objects)
    if 'dependencies' in ace :
        for dependency in ace['dependencies'] :
            linker_args.append("-Wl,-force_load")
            dependency_ace = json.load(open(os.path.expanduser("~/.ace/%s/ace.json" %dependency['name'])))
            # pprint(dependency_ace)
            linker_args.append(os.path.expanduser("~/.ace/%s/%s.a" %(dependency['name'],dependency_ace['target'])));
    run_cmd(linker_args)

# Link an ace program
def link(ace,args,objects):
    linker_args=["g++"];
    linker_args.append("-o")
    linker_args.append(ace['target'])
    linker_args.extend(objects)
    if 'dependencies' in ace :
        for dependency in ace['dependencies'] :
            linker_args.append("-Wl,-force_load")
            dependency_ace = json.load(open(os.path.expanduser("~/.ace/%s/ace.json" %dependency['name'])))
            # pprint(dependency_ace)
            linker_args.append(os.path.expanduser("~/.ace/%s/%s.a" %(dependency['name'],dependency_ace['target'])));
    run_cmd(linker_args)

def archive(ace,args,objects):
    target="%s.a" %ace['target']
    if os.path.exists(target):
        os.remove(target)
    linker_args=["ar"];
    linker_args.append("-rcs")
    linker_args.append(target)
    for object in objects:
        linker_args.append(object)
    run_cmd(linker_args)
    
if __name__ == "__main__":
    main(sys.argv[1:])
