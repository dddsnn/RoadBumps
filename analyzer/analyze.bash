#!/bin/bash

if [ -z "${1}" ] ; then
    echo "Specify a .fit file in ./fit to analyze."
    exit 1
fi
file_name=$(basename ${1})
echo ${file_name}
if [ ! -f "./fit/${file_name}" ] ; then
    echo "File ${file_name} doesn't exist in ./fit/"
    exit 1
fi

docker-compose build
docker-compose run --rm -v $(pwd)/fit:/fit analyze "/fit/${file_name}"
