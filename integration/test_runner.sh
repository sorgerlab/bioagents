#!/usr/bin/env bash
if [ "$1" != "" ]; then
  cat $1 | nc 127.0.0.1 6200
else
  nc 127.0.0.1 6200
fi
