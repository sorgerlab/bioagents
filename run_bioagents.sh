# SET THE PATH BELOW TO TRIPS.KQML.jar
#
# export CLASSPATH="TRIPS.KQML.jar":$CLASSPATH
#
# IF INDRA IS NOT ON THE PATH, SET IT BELOW TO THE PATH OF THE INDRA FOLDER
#
# export PYTHONPATH="indra":$PYTHONPATH
#
python dtda_module.py &
python mra_module.py &
python mea_module.py &
