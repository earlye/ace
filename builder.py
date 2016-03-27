from __future__ import print_function

import argparse
import glob
import json
import os
import platform
import re
import shutil
import string
import sys
import time

from pprint import pprint
from run_cmd import run_cmd
from utils import *



class Builder(object) :

    @staticmethod
    def merge(a, b, path=None):
        "merges b into a"
        if path is None:
            path = []
        for key in b:
            if key in a:
                if isinstance(a[key], dict) and isinstance(b[key], dict):
                    merge(a[key], b[key], path + [str(key)])
                elif a[key] == b[key]:
                    pass # same leaf value
                else:
                    raise Exception('Conflict at %s' % '.'.join(path + [str(key)]))
            else:
                a[key] = b[key]
        return a                                            

    @staticmethod
    def load_config(args):
        ace_dir=os.path.dirname(os.path.realpath(__file__))
        config_paths = [
            os.path.join(ace_dir,"ace.conf.json"),            
            "/usr/local/etc/ace.conf.json"
        ]
        config_paths.extend( glob.glob( "/etc/default/ace.d/*.conf.json" ) )
        config_paths.extend( glob.glob( os.path.expanduser( "~/.etc/ace.d/*.conf.json" )))
        config = {}
        for config_path in config_paths:
            if os.path.exists(config_path):
                more_config = json.load(open(config_path,"r"))
                Builder.merge(config,more_config)
        return config

    def detect_gpp(self) :
        gpp_version = run_cmd(["g++", "--version"], echo=False)
        gpp_version_string = gpp_version.stdout[0]        
        for key,value in self.config['g++-version-map'].iteritems():
            if key==gpp_version_string:
                return self.config['g++-versions'][value]
        gpp_default = self.config['g++-version-map']['default']
        print("WARN: unrecognized g++ version \"%s\". Using default \"%s\" instead" %(gpp_version_string, gpp_default))
        return self.config['g++-versions'][gpp_default]
        

    def run(self):
        self.descend(self.args['build_dir']);
    
    def __init__(self,argv):
        # pprint({
        #     "__file__":__file__,
        #     "realpath":os.path.realpath(__file__),
        #     "args":args,
        #     "os.name":os.name,
        #     "sys.platform":sys.platform,
        #     "platform.platform":platform.platform()
        # })
        parser = argparse.ArgumentParser()
        parser.add_argument('-d','--dir',dest='build_dir',default='.',help='directory to build in.');
        parser.add_argument('-r','--rebuild',dest='rebuild',action='store_true',default=False,help='Rebuild everything.');
        parser.add_argument('-nc','--no-clone-missing',dest='clone-missing',action='store_false',default=True,help='Disable clone of missing repos when building containers.');
        self.args = vars(parser.parse_args(argv))

        self.config = Builder.load_config(self.args)
        self.gpp = self.detect_gpp()
        pprint({"self":self.__dict__})


    # Descend into a directory and continue building there.
    def descend(self,target_dir):
        if (target_dir=='.'):
            return self.build();        
        print( "Entering directory `" + target_dir + "'", file=sys.stderr)
        try:
            os.chdir(target_dir);
            self.build();
        finally:
            if not(target_dir == '.'):
                os.chdir("..")
                print( "Leaving directory `" + target_dir + "'", file=sys.stderr)

    # Build in the current directory
    def build(self):
        if os.path.exists("ace.json"):
            return self.build_ace()
        if os.path.exists("Makefile"):
            return self.build_make();
        if os.path.exists("pom.xml"):
            return self.build_maven();
        return self.build_ace_container(None);
                
    # Build in the current directory based on ace.json
    def build_ace(self):
        ace = json.load(open("ace.json"))
        
        if not 'include_dirs' in ace:
            ace['include_dirs'] = [];
            
        ace['need_link'] = False;
        
        if os.path.isdir("include") :
            ace['include_dirs'].append("include")
        
        print( "-- Building \"%s\" with ACE" %ace['type'] )
        if ace['type'] == 'program' :
            self.build_ace_program(ace)
        elif ace['type'] == 'library' :
            self.build_ace_library(ace)
        elif ace['type'] == 'container' :
            self.build_ace_container(ace)
        else:
            print("unrecognized type:\"%s\"" %ace['type'])


    # Build in the current directory, based on it being just a container of other projects
    def build_ace_container(self,ace):
        print( "-- Building as ace container" )
        if self.args['clone-missing'] and not ace == None and 'modules' in ace:
            print( "-- checking for missing repos" )
            for module in ace['modules']:
                if not os.path.isdir(module):
                    moduleDefinition = ace['modules'][module];
                    print( "--- Need to clone module: %s"  %module )
                    if "git-remotes" in  moduleDefinition:
                        if not "origin" in moduleDefinition["git-remotes"]:
                            raise Exception("Module \"" + module + "\" has git-remotes info, but no origin. Could not clone it.")
                        run_cmd(["git","clone",moduleDefinition["git-remotes"]["origin"],module]);
                    else:
                        raise Exception("Module \"" + module + "\" has no repository info and is missing. Could not clone it.")

        for item in os.listdir("."):
            if not item.startswith('.') :
                if os.path.isdir(item) :
                    self.descend(item)

    # Build an ace library
    def build_ace_library(self,ace):
        print( "-- Building library with ACE" )
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
            source_objects.append(self.compile_module(ace,file))

        if not os.path.exists("%s.a" %ace['target']):
            ace['need_link'] = True

        if ace['need_link'] :
            self.archive(ace,source_objects)

        # Build test modules...
        for file in test_modules:
            test_objects.append(self.compile_module(ace,file))
        for object in test_objects:
            self.scan_object_for_tests(object,test_methods);

        test_objects.append(self.generate_test_harness(ace,test_methods));
        self.link_test_harness(ace,source_objects,test_objects)
        run_cmd(["./.test_harness.exe"]);


        # install the library in ~/.ace/
        path = "~/.ace/%s" %ace['name']
        path = os.path.expanduser(path)
        print( "Installing library to %s" %path )
        if os.path.isdir(path):
            shutil.rmtree(path)
        os.makedirs(path)
        shutil.copytree("include" , "%s/include" %(path))
        shutil.copyfile("%s.a" %ace['target'], "%s/%s.a" %(path,ace['target']))
        json.dump(ace,open("%s/ace.json" %path,"w"))
        run_cmd(["find", path, "-type" , "f"])

    # Compile a single module
    def compile_module(self,ace,path):
        target_file = replace_extension(path,".o")
        if not self.module_needs_compile(ace,path) :
            print( "-- Skipping: " + path )
            return target_file
        print( "-- Compiling: " + path )
        compiler_args=["g++"];
        compiler_args.extend(self.gpp['options'])
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
        
    def module_needs_compile(self,ace,path) :
        if self.args['rebuild'] :
            print( "-- %s needs compile. -r specified." %path )
            return True

        dependency_file = replace_extension(path,".d")
        if not os.path.isfile(dependency_file) :
            print( "-- %s needs compile. No dependency information found" %path )
            return True

        target_file = replace_extension(path,".o")
        if not os.path.isfile(target_file) :
            print( "-- %s needs compile. Target does not exist" %path )
            return True

        source_time = os.path.getmtime(path)
        dependency_time = os.path.getmtime(dependency_file)
        if source_time > dependency_time:
            print( "-- %s needs compile. Source timestamp > Dependency timestamp" %path )
            return True

        target_time = os.path.getmtime(target_file)
        if source_time > target_time:
            print( "-- %s needs compile. Source timestamp > Target timestamp" %path )
            return True

        dependencies = self.read_dependency_file(dependency_file)
        for dependency in dependencies:
            if not os.path.exists(dependency) :
                print( "-- Module needs compile: \"%s\" does not exist" %dependency )
                return True
            dependency_time = os.path.getmtime(dependency)
            if dependency_time > target_time:
                print( "-- Module needs compile: %s newer than %s\n\t(%s vs %s)" %(dependency,target_file,dependency_time,target_time) )
                return True

        return False

    def archive(self,ace,objects):
        target="%s.a" %ace['target']
        if os.path.exists(target):
            os.remove(target)
        linker_args=["ar"];
        linker_args.append("-rcs")
        linker_args.append(target)
        for object in objects:
            linker_args.append(object)
        run_cmd(linker_args)
    
    def scan_object_for_tests(self,object,test_methods):
        functions = self.scan_object_for_functions(object)
        for function in functions :
            if function.endswith("()") and (function.startswith("test") or "::test" in function):
                test_methods.append(function)

    def scan_object_for_functions(self,object):
        ace_dir=os.path.dirname(os.path.realpath(__file__))
        method_lister=os.path.join(ace_dir,"method_list")
        args = [method_lister,object];
        result = run_cmd(args)
        return result.stdout
                
    def generate_test_harness(self,ace,test_methods) :
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
        return self.compile_module(ace,".test_harness.cpp")

    def link_test_harness(self,ace,source_objects,test_objects):
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
    
    # Build ace program
    def build_ace_program(self,ace):
        print( "-- Building program with ACE" )
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
            source_objects.append(self.compile_module(ace,file))
        if not os.path.exists(ace['target']):
            ace['need_link'] = True
        if ace['need_link'] :
            self.link(ace,source_objects)

        # Build test modules...
        for file in test_modules:
            test_objects.append(self.compile_module(ace,file))
        for object in test_objects:
            self.scan_object_for_tests(object,test_methods);

        nomain_source_objects = filter(self.nomain,source_objects)

        test_objects.append(self.generate_test_harness(ace,test_methods));
        self.link_test_harness(ace,nomain_source_objects,test_objects)
        run_cmd(["./.test_harness.exe"]);

    def nomain(self,object) :
        functions = self.scan_object_for_functions(object)
        return "_main()" in functions

    def build_make(self):
        print( "-- Building make project" )
        make_args=["make"]
        run_cmd(make_args)

    def read_dependency_file(self, filename):
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

    # Link an ace program
    def link(self,ace,objects):
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
