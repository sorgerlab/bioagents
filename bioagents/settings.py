__all__ = ['IMAGE_DIR', 'TIMESTAMP_PICS']

from os import path, mkdir

# Select the directory where images are stored. By default, it is in a
# directory called `images` alongside this file. Note that if this file does
# not exist, it will be created. The path should be an absolute path.
IMAGE_DIR = path.abspath(path.join(path.dirname(__file__), 'images'))

if not path.exists(IMAGE_DIR):
    mkdir(IMAGE_DIR)

# Choose whether images are given a timestamp. This can cause a buildup of
# images over time, however it guarantees overall uniqueness over a single run.
TIMESTAMP_PICS = False
