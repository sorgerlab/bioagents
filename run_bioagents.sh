#!/usr/bin/env bash
# IF INDRA IS NOT ON THE PATH, SET IT BELOW TO THE PATH OF THE INDRA FOLDER
#
export PYTHONPATH=".:$HOME/Dropbox/postdoc/src/indra":$PYTHONPATH
#
echo $PYTHONPATH
python bioagents/dtda/dtda_module.py &
python bioagents/mra/mra_module.py &
python bioagents/mea/mea_module.py &
