#!/bin/bash -e -x

if [[ ! -d /usr/local/bin ]]; then
    mkdir -p /usr/local/bin
fi

if [[ ! -f /usr/local/bin/ace ]]; then
    ln -s $(pwd)/ace /usr/local/bin/ace
else
    ls -l /usr/local/bin/ace
fi

