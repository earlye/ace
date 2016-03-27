import os

def replace_extension(filename,new_extension) :
    base_file, ext = os.path.splitext(filename)
    return base_file + new_extension
