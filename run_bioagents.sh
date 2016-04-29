#!/usr/bin/env bash
# SET THE PATH BELOW TO TRIPS.KQML.jar
#
export CLASSPATH="$HOME/src/bob/etc/java/TRIPS.KQML.jar":$CLASSPATH
#
# IF INDRA IS NOT ON THE PATH, SET IT BELOW TO THE PATH OF THE INDRA FOLDER
#
export PYTHONPATH=".:$HOME/Dropbox/postdoc/src/indra":$PYTHONPATH
#
echo $PYTHONPATH
echo $CLASSPATH
python bioagents/dtda/dtda_module.py &
python bioagents/mra/mra_module.py &
python bioagents/mea/mea_module.py &
