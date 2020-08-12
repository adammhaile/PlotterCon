import os
import sys
import glob
import re
import shutil

path = sys.argv[1]
search = os.path.join(path, '*.jpeg')
out_path = os.path.join(path, 'rename')
os.makedirs(out_path, exist_ok=True)
for f in glob.glob(search):
    fn = f.replace(path, '').replace('Z', ',').replace('X', ',').replace('Y', ',').replace('.jpeg', '')
    _, z, x, y = re.split(',', fn)
    name = f'Z{z}Y{y}X{x}.jpeg'
    name = os.path.join(out_path, name)
    print(f'{f} -> {name}')
    shutil.copy(f, name)