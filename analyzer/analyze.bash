#!/bin/bash

if [ -n "$1" ] ; then
    file_name=$(basename "$1")
    if [ ! -d "./fit/$file_name" ] ; then
        echo "File $file_name doesn't exist in ./fit/"
        exit 1
    fi
else
    file_name=
fi

docker-compose build
docker-compose run --rm -v ./fit:/fit analyze $file_name
