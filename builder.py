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

from joblib import delayed, Parallel
from pprint import pprint
from run_cmd import run_cmd
from utils import *


def compileAModule(builder,ace,filename):
    return builder.compile_module(ace,filename);

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
        gpp_version = run_cmd(["g++", "--version"], echo=True, echoErr=False)
        gpp_version_string = gpp_version.stdout[0]
        print(f"detecting g++: {gpp_version_string}")
        print(f"config: {self.config['g++-version-map']}")
        for key,value in self.config['g++-version-map'].items():
            if key==gpp_version_string:
                print("Found g++ version \"%s\"" %(gpp_version_string))
                return self.config['g++-versions'][value]
        gpp_default = self.config['g++-version-map']['default']
        print("WARN: unrecognized g++ version \"%s\". Using default \"%s\" instead" %(gpp_version_string, gpp_default))
        return self.config['g++-versions'][gpp_default]


    def run(self):
        self.descend(self.args.build_dir);

    def __init__(self,argv):
        # pprint({
        #     "__file__":__file__,
        #     "realpath":os.path.realpath(__file__),
        #     "args":args,
        #     "os.name":os.name,
        #     "sys.platform":sys.platform,
        #     "platform.platform":platform.platform()
        # })
        print("Ace version 0.4")
        parser = argparse.ArgumentParser()
        parser.add_argument('-d','--dir',dest='build_dir',default='.',help='directory to build in.');
        parser.add_argument('-r','--rebuild',dest='rebuild',action='store_true',default=False,help='Rebuild everything.');
        parser.add_argument('-c','--coverage',dest='coverage',action='store_true',default=False,help='Run coverage.');
        parser.add_argument('-nc','--no-clone-missing',dest='clone_missing',action='store_false',default=True,help='Disable clone of missing repos when building containers.');
        self.args = parser.parse_args(argv)

        self.config = Builder.load_config(self.args)
        self.gpp = self.detect_gpp()
        # pprint({"self":self.__dict__})

    def generateCoverageSite(self):
        print("Processing Coverage Data")

        print("- Building trace file")
        run_cmd(["lcov", "-c", "-d" , ".", "-o", ".test_harness.coverage"], echo=False)
        print("- Removing library traces")
        run_cmd(["lcov", "-r", ".test_harness.coverage", "/usr/*", "-o", ".test_harness.coverage"], echo=False)
        run_cmd(["lcov", "-r", ".test_harness.coverage", "/Applications/*", "-o", ".test_harness.coverage"], echo=False)
        print("- Removing test code traces")
        run_cmd(["lcov", "-r", ".test_harness.coverage", "*/src/test/*", "-o", ".test_harness.coverage"], echo=False)
        print("- Generating coverage site")
        run_cmd(["genhtml", "-o", ".coverage", ".test_harness.coverage"], echo=False)

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
                print( "\n\nLeaving directory `" + target_dir + "'", file=sys.stderr)

    # Build in the current directory
    def build(self):
        if os.path.exists("ace.json"):
            return self.build_ace()
        if os.path.exists("Makefile"):
            return self.build_make();
        if os.path.exists("pom.xml"):
            return self.build_maven();
        return self.build_ace_container(None);

    def expandDependencies(self,dependencies,destination = None):
        result = destination if destination else []
        print("---- expanding dependencies:{} into destination:{}".format(dependencies,result))
        for dependency in dependencies:
            if not dependency in result:
                result.append(dependency)
                print("---- expanding dependency:{}".format(dependency))
                dependency_ace_filename = "~/.ace/{}/ace.json".format(dependency['name'])
                print("---- expanding dependency:{}".format(dependency_ace_filename))
                dependency_ace_filename = os.path.expanduser(dependency_ace_filename)
                print("---- expanding dependency:{}".format(dependency_ace_filename))
                dependency_ace = json.load(open(dependency_ace_filename))
                if 'dependencies' in dependency_ace:
                    print("----- child {} dependencies:{}".format(dependency,dependency_ace['dependencies']))
                    self.expandDependencies(dependency_ace['dependencies'],result)
        return result

    # Build in the current directory based on ace.json
    def build_ace(self):
        ace = json.load(open("ace.json"))

        if not 'include_dirs' in ace:
            ace['include_dirs'] = [];

        ace['need_link'] = False;

        if os.path.isdir("include") :
            ace['include_dirs'].append("include")

        if 'dependencies' in ace :
            ace['expandedDependencies'] = self.expandDependencies(ace['dependencies'])
        else:
            ace['expandedDependencies'] = []
        print("--- expanded dependencies:{}".format(ace['expandedDependencies']))

        if 'dependencies' in ace:
            for dependency in ace['expandedDependencies']:
                print("--- adding include path for dependency: {}".format(dependency))
                path = "~/.ace/%s/include" %dependency['name']
                path = os.path.expanduser(path)
                ace['include_dirs'].append(path)


        if 'children' in ace:
            for child in ace['children']:
                self.descend(child)

        aceType = ace['type']
        print( "-- Building \"%s\" with ACE" %aceType )
        if aceType == 'program' :
            self.build_ace_program(ace)
        elif aceType == 'library' :
            self.build_ace_library(ace)
        elif aceType == 'container' :
            self.build_ace_container(ace)
        elif aceType == 'make' :
            self.build_make();
        else:
            print("unrecognized type:\"%s\"" %ace['type'])


    # Build in the current directory, based on it being just a container of other projects
    def build_ace_container(self,ace):
        print( "-- Building as ace container" )
        if self.args.clone_missing and not ace == None and 'modules' in ace:
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

        print( "-- Scanning directory" )
        for item in os.listdir("."):
            if not item.startswith('.') :
                if os.path.isdir(item) :
                    self.descend(item)

    def resetCoverageData(self):
        if self.args.coverage:
            print("Resetting coverage data")
            for root, dirs, files in os.walk("./"):
                for file in files:
                    if file.endswith(".gcda"):
                        fullName = os.path.join(root,file)
                        os.remove(fullName)

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
        # pprint({"source_modules":source_modules,"test_modules":test_modules})

        # Build source modules...
        source_objects=[];
        #for file in sorted(source_modules):
        #    source_objects.append(self.compile_module(ace,file))

        print("Compiling source modules")
        source_objects = Parallel(n_jobs=4)(
            delayed(compileAModule)(self,ace,fileName)
            for fileName in source_modules)

        print("Linking library")
        if len(source_objects) or not os.path.exists("%s.a" %ace['target']):
            ace['need_link'] = True

        archive = None
        if ace['need_link'] :
            archive = self.archive(ace,source_objects)

        # Build test modules...
        print("Running library tests")
        for file in test_modules:
            test_objects.append(self.compile_module(ace,file))

        print("Scanning for test objects")
        for object in test_objects:
            self.scan_object_for_tests(object,test_methods);

        print("Generating test_objects")
        test_objects.append(self.generate_test_harness(ace,test_methods));
        print("Linking test harness")
        self.link_test_harness(ace,source_objects,test_objects)


        self.runTestHarness()

        # install the library in ~/.ace/
        path = "~/.ace/%s" %ace['name']
        path = os.path.expanduser(path)
        print( "Installing library to %s" %path )
        if os.path.isdir(path):
            shutil.rmtree(path)
        print( "Making directory %s" %path )
        os.makedirs(path)
        print( "Copying includes to %s/include" %path )
        try:
            shutil.copytree("include" , "%s/include" %(path))
        except Exception as e:
            print("Well, that sucks.")
            print(e)
        print ("Done with that...")
        if archive is not None:
            print( "Copying archive to %s/%s" %(path,archive) )
            shutil.copyfile("%s" %archive, "%s/%s" %(path,archive))
        print ("Dumping ace.json...")
        json.dump(ace,open("%s/ace.json" %path,"w"))
        print ("Running find...")
        run_cmd(["find", path, "-type" , "f"])

    def runTestHarness(self):
        if self.args.coverage:
            self.resetCoverageData()
        run_cmd(["./.test_harness.exe"]);
        if self.args.coverage:
            self.generateCoverageSite()

    # Compile a single module
    def compile_module(self,ace,path):
        try:
            ace_dir=os.path.dirname(os.path.realpath(__file__))
            target_file = replace_extension(path,".o")
            if not self.module_needs_compile(ace,path) :
                # print( "-- Skipping: " + path )
                return target_file
            print( "-- Compiling: " + path )
            compiler_args=["g++"];
            compiler_args.extend(self.gpp['options'])
            compiler_args.append("-MD") # generate .d file
            compiler_args.append("-c") # compile, too!
            compiler_args.append("-g3") # include debug symbols.
            if self.args.coverage:
                compiler_args.append("--coverage") # code coverage
                compiler_args.append("-O0")
            else:
                compiler_args.append("-O3")

            compiler_args.append("-Werror=return-type")
            compiler_args.append("-I{}".format(os.path.join(ace_dir,"include")))
            compiler_args.append("-o")
            compiler_args.append(target_file)
            for include_path in ace['include_dirs']:
                compiler_args.append("-I%s" %include_path);
            compiler_args.append(path)
            run_cmd(compiler_args)
            ace['need_link'] = True
            return target_file
        except Exception as e:
            print(f"-- Failed to build {path}")
            print(e)
            raise e

    def module_needs_compile(self,ace,path) :
        if self.args.rebuild :
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
        #linker_args.append("--no_warning_for_no_symbols")
        linker_args.append("-rcs")
        linker_args.append(target)
        for object in objects:
            linker_args.append(object)
        run_cmd(linker_args)
        return target

    def scan_object_for_tests(self,obj,test_methods):
        functions = self.scan_object_for_functions(obj)
        filteredFunctions = list(filter(lambda function: function.endswith("()") and (function.startswith("test") or "::test" in function or " test" in function), functions))
        test_methods.extend(filteredFunctions)

    def scan_object_for_functions(self,obj):
        ace_dir=os.path.dirname(os.path.realpath(__file__))
        method_lister=os.path.join(ace_dir,"method_list")
        args = [method_lister,obj];
        result = run_cmd(args,echo=False)
        return result.stdout

    def generate_test_harness(self,ace,test_methods) :
        print(f"generating test harness: {test_methods}")
        variables = {};
        variables['automatically_generated'] = "Automatically generated by ACE @" + time.ctime();
        variables['test_declarations'] = [];
        variables['test_list'] = [];
        for test_method in test_methods:
            # print(f"generating call to {test_method}")
            parts = list(filter(len,test_method.split(':')))
            # print(f"- parts:{parts}")
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

        print("Generating test harness...")
        ace_dir=os.path.dirname(os.path.realpath(__file__))
        template_name=os.path.join(ace_dir,"cpp_test_template.cpp")
        template = string.Template(open(template_name).read())
        test_harness = template.substitute(variables)
        print("Writing test harness...")
        open(".test_harness.cpp","w").write(test_harness)
        print("Building test harness...")
        return self.compile_module(ace,".test_harness.cpp")

    def link_test_harness(self,ace,source_objects,test_objects):
        ace_dir=os.path.dirname(os.path.realpath(__file__))
        linker_args=["g++"]
        if self.args.coverage:
            coverageArgs = self.gpp.get("linker-coverage-args",[])
            print(f"Linking with coverage:{coverageArgs}")
            linker_args.extend(coverageArgs)
        linker_args.extend(["-g3",
                            "-rdynamic",
                            "-o",".test_harness.exe"]) #,".test_harness.o"])
        linker_args.extend(source_objects)
        linker_args.extend(test_objects)
        needRunTest = True
        for x in source_objects:
            if self.hasAceRunTest(x):
                print("Using {} for ace::run_test".format(x))
                needRunTest = False
        for x in test_objects:
            if self.hasAceRunTest(x):
                print("Using {} for ace::run_test".format(x))
                needRunTest = False

        dependency_flags = set()
        if 'dependencies' in ace :
            for dependency in ace['expandedDependencies'] :
                dependency_ace = json.load(open(os.path.expanduser("~/.ace/%s/ace.json" %dependency['name'])))
                if ('header-only' in dependency_ace) and dependency_ace['header-only']:
                    continue;
                if 'dependency-flags' in dependency_ace:
                    dependency_flags.update(dependency_ace['dependency-flags'])
                ## Grab any linker options that have to be applied before including a library.
                linker_args.extend(self.gpp['library-options'])
                libraryFile = os.path.expanduser("~/.ace/%s/%s.a" %(dependency['name'],dependency_ace['target']))
                if self.hasAceRunTest(libraryFile):
                    print("Using library {} for ace::run_test".format(libraryFile))
                    needRunTest = False

                linker_args.append(libraryFile);
        if 'lflags' in ace:
            linker_args.extend(ace['lflags']);
        if 'dependency-flags' in ace:
            dependency_flags.update(ace['dependency-flags']);

        if needRunTest:
            shutil.copy(os.path.join(ace_dir,"cpp_test_run.cpp"),".test_run.cpp")
            self.compile_module(ace,".test_run.cpp")
            linker_args.append(".test_run.o")

        linker_args.extend(dependency_flags)
        linker_args.extend(self.gpp['linker-final-options'])
        run_cmd(linker_args,echo=True)

    # Build ace program
    def build_ace_program(self,ace):
        print( "-- Building program with ACE" )
        source_modules=[]
        source_objects=[]
        test_modules=[]
        test_objects=[]
        test_methods=[]
        for root, dirs, files in os.walk("src/main"):
            for file in files:
                if file.endswith(".cpp") or file.endswith(".cxx") :
                    source_modules.append(os.path.join(root,file))
        for root, dirs, files in os.walk("src/test"):
            for file in files:
                if file.endswith(".cpp") or file.endswith(".cxx") or file.endswith(".C"):
                    test_modules.append(os.path.join(root,file))
        # pprint({"source_modules":source_modules,"test_modules":test_modules})
        source_objects=[];
        for file in source_modules:
            source_object = self.compile_module(ace,file)
            source_objects.append(source_object)
        self.link(ace,source_objects)

        # Build test modules...
        for file in test_modules:
            test_objects.append(self.compile_module(ace,file))
        for object in test_objects:
            self.scan_object_for_tests(object,test_methods);

        print("removing main source objects")
        nomain_source_objects = filter(self.nomain,source_objects)

        test_objects.append(self.generate_test_harness(ace,test_methods));
        self.link_test_harness(ace,nomain_source_objects,test_objects)

        self.runTestHarness()

    def nomain(self,object) :
        functions = self.scan_object_for_functions(object)
        present = ("_main()" in functions) or ("_main" in functions) or ("main" in functions)
        return not present;

    def hasAceRunTest(self,oFile):
        functions = self.scan_object_for_functions(oFile)
        present = ("ace::run_test(ace::test const&, ace::stats&)" in functions)
        if (not present and "run_test" in oFile):
            pprint(functions)
        return present

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
        need_link = ace['need_link']
        linker_args=["g++"];
        linker_args.append("-rdynamic")
        linker_args.append("-o")
        linker_args.append(ace['target'])
        linker_args.extend(objects)
        if not os.path.exists(ace['target']):
            need_link = True
            target_time = 0
        else:
            target_time = os.path.getmtime(ace['target'])

        dependency_flags = set()
        if 'dependencies' in ace :
            for dependency in ace['expandedDependencies'] :
                dependency_ace = json.load(open(os.path.expanduser("~/.ace/%s/ace.json" %dependency['name'])))
                if ('header-only' in dependency_ace) and dependency_ace['header-only']:
                    continue;

                print("-- dependency_ace:{}".format(dependency['name']))
                pprint(dependency_ace)
                library_file = os.path.expanduser("~/.ace/%s/%s.a" %(dependency['name'],dependency_ace['target']));
                linker_args.extend(self.gpp['library-options'])
                linker_args.append(library_file);
                if 'dependency-flags' in dependency_ace:
                    dependency_flags.update(dependency_ace['dependency-flags'])
                dependency_time = os.path.getmtime(library_file)
                if dependency_time > target_time:
                    print( "-- Needs link: %s newer than %s\n\t(%s vs %s)" %(library_file,ace['target'],dependency_time,target_time) )
                    need_link = True;

        linker_args.extend(dependency_flags)
        linker_args.extend(self.gpp['linker-final-options'])
        if need_link:
            run_cmd(linker_args,echo="True")
