import os, subprocess, sys, platform

def color(text, color_name):
  if sys.platform.startswith('win'):
    return text

  colors = {}
  colors['pink'] = '\033[95m'
  colors['blue'] = '\033[94m'
  colors['green'] = '\033[92m'
  colors['yellow'] = '\033[93m'
  colors['red'] = '\033[91m'
  end = '\033[0m'

  if color_name in colors.keys():
      text = colors[color_name] + text + end

  return text

def split_cmd(start, files, end = ''):
  cmds = []
  start = start + ' '
  end = ' ' + end

  buffer = start
  
  while len(files) > 0:
    if len(buffer) + len(files[0]) + len(end) + 3 < 32000:
      buffer = buffer + ' "' + files.pop(0) + '"'
    else:
      buffer = buffer + end.rstrip()
      cmds.append(buffer)
      buffer = start
  
  buffer = buffer + end.rstrip()
  cmds.append(buffer)

  return cmds

def separate_cmd(cmd):
  cmd = list(cmd)
  buffer = ''
  out = []
  switch = [False, '']

  for x in range(len(cmd)):
    char = cmd[x]
    
    if char == ' ' and not switch[0]:
      out.append(buffer)
      buffer = ''
    # Be wary of a single/double quote that is part of a filename and not part of an
    # enclosing pair
    elif (char == '"' or char == "'") and not switch[0]:
      if (char in cmd[x + 1:]) and (buffer == ''):
        switch[0] = True
        switch[1] = char
      else:
        buffer = buffer + char
    elif char == switch[1] and switch[0]:
      out.append(buffer)
      buffer = ''
      switch[0] = False
    else:
      buffer = buffer + char
  out.append(buffer)

  # Just in case there were multiple spaces.
  while '' in out:
    out.remove('')

  return out

def simple_exec(cmd):
  cmd = separate_cmd(cmd)
  
  with open(os.devnull, 'w') as void:
    sub = subprocess.Popen(cmd, shell = False, stdout = void, stderr = void)
    
    return int(sub.wait())

def execute(cmd, capture = False):
  if platform.system() == 'Windows':
    cmd = 'bin\\' + cmd
  
  with open(os.devnull, 'w') as void:
    if capture:
      sub = subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE, stderr = void)
    else:
      sub = subprocess.Popen(cmd, shell = True, stdout = void, stderr = void)
  
  status = sub.wait()

  # Exit if the command fails for any reason.
  if status != 0:
    print('err: utils.execute(): command exited with bad status.\ncmd = {0}\nexit status = {1}'.format(cmd, status))

  if capture:
    text = sub.stdout.read()
    return text
  else:
    return None

def list_files(directory = '.', contains = None, extension = None):
  """
  Find all files in a given directory that match criteria.
  """
  
  tmp = os.listdir(directory)
  contents = []
  
  for path in tmp:
    path = os.path.join(directory, path)
    
    if os.path.isfile(path):
      contents.append(path)
  
  contents.sort()

  if contains is not None:
    remove = []
    
    for file in contents:
      if contains not in file:
        remove.append(file)
    
    for file in remove:
      contents.remove(file)

  if extension is not None:
    remove = []
    
    for file in contents:
      ext = file.split('.')[-1]
      
      if extension.lower() != ext.lower():
        remove.append(file)
    
    for file in remove:
      contents.remove(file)

  return contents

def is_executable(command):
  if get_executable_path(command) is not None:
    return True
  else:
    return False


def get_executable_path(command):
  # Add extension if on the windows platform.
  if sys.platform.startswith('win'):
    pathext = os.environ['PATHEXT']
  else:
    pathext = ''

  for path in os.environ['PATH'].split(os.pathsep):
    if os.path.isdir(path):
      for ext in pathext.split(os.pathsep):
        name = os.path.join(path, command + ext)
        
        if (os.access(name, os.X_OK)) and (not os.path.isdir(name)):
          return name

  return None

def cpu_count():
  num = 0

  if sys.platform.startswith('win'):
    try:
      num = int(os.environ['NUMBER_OF_PROCESSORS'])
    except (ValueError, KeyError):
      pass
  elif sys.platform == 'darwin':
    try:
      num = int(os.popen('sysctl -n hw.ncpu').read())
    except ValueError:
      pass
  else:
    try:
      num = os.sysconf('SC_NPROCESSORS_ONLN')
    except (ValueError, OSError, AttributeError):
      pass

  if num >= 1:
    return num
  else:
    return 1