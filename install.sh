#!/bin/bash
set -e
set -x

if [[ ! -d /usr/local/bin ]]; then
    mkdir -p /usr/local/bin
fi

if [[ ! -f /usr/local/bin/ace ]]; then
    ln -s $(pwd)/ace /usr/local/bin/ace
fi

# ACE IS INSTALLED HERE
ls -l /usr/local/bin/ace

