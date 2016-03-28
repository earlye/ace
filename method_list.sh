#!/bin/bash
case "$(uname)" in
    'Darwin') # OSX
	nm -just-symbol-name -defined-only $1 | c++filt
	;;

    'Linux') # UBUNTU: Linux
	nm -g --defined-only $1 | sed -r "s/^.{19}//" | c++filt
	;;

    *) # DEFAULT
	nm -g --defined-only $1 | sed -r "s/^.{19}//" | c++filt
	;;
esac


