#!/usr/bin/env bash

aptget_update()
{
    if [ ! -z $1 ]; then
        echo ""
        echo "Retrying apt-get update..."
        echo ""
    fi
    output=`sudo apt-get update 2>&1`
    echo "$output"
    if [[ $output == *[WE]:\ * ]]; then
        return 1
    fi
}
aptget_update || aptget_update retry || aptget_update retry

set -e

sudo apt-get -qq install libffi-dev python-dev
