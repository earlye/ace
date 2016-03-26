#!/bin/bash
nm -just-symbol-name -defined-only $1 | c++filt

