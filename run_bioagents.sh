#!/usr/bin/env bash
# IF INDRA IS NOT ON THE PATH, SET IT BELOW TO THE PATH OF THE INDRA FOLDER
#
export PYTHONPATH=.:$HOME/Dropbox/postdoc/darpa/src/indra

trap cleanup 0 1 2 3 15

python bioagents/dtda/dtda_module.py &
dtda_pid=$!
python bioagents/mra/mra_module.py &
mea_pid=$!
python bioagents/mea/mea_module.py &
mra_pid=$!

cleanup () {
    kill -9 $dtda_pid
    kill -9 $mea_pid
    kill -9 $mra_pid
    }

wait
