"""
Fabric file for deploying the project.

Main commands are:

`fab setup`: Setup the server.

`fab golive`: Deploys on the live server.

"""

from fabric.api import env, run, cd, local, task, sudo
from fabric.contrib.files import append

from fabtools import require, supervisor
from fabtools.python import virtualenv

## Change this

APPNAME = "cnll.fr"
SERVERNAME = "cnll.fr"
BASE_DIR = APPNAME
PORT = 5700

NATIVE_PACKAGES = [
  "git",
  "libjpeg-dev",
  "make",
  "python-dev",
  "python-pip",
  "supervisor",
]

RSYNC_OPTIONS = "--delete-after"
RSYNC_EXCLUDES = "--exclude env --exclude .git --exclude .tox --exclude .idea"


# Default target
env.hosts = ['dedibox.yaka.biz']
env.user = 'fermigier'
env.SERVERNAME = SERVERNAME
env.target_dir = BASE_DIR
env.app_name = APPNAME


## Everything below should be fairly generic (TODO: move to a library).

NGINX_TPL = """
server {
  listen              80;
  server_name         %(server_name)s www.%(server_name)s;

  access_log /var/log/nginx/%(server_name)s-access.log;

  location /static/ {
    root %(staticroot)s;
  }

  location / {
    proxy_pass            http://localhost:%(port)d/;
    include               /etc/nginx/proxy_params;
    client_max_body_size  50M;

    rewrite ^/sites/default/files/(.*) /static/old/$1 permanent;
    rewrite ^/enquete(.*) http://62.210.119.93/enquete/index.php/survey/index/sid/365225/lang/fr/;
  }
}

"""


#
# Environment massaging
#
@task
def vagrant():
  # connect to the port-forwarded ssh
  env.hosts = ['127.0.0.1:2222']
  env.user = 'vagrant'

  # use vagrant ssh key
  result = local('vagrant ssh-config | grep IdentityFile', capture=True)
  env.key_filename = result.split()[1]


def make_absolute(path):
  if not path.startswith("/"):
    path = "/home/%s/%s" % (env.user, path)
  return path


#
# Setup commands
#
@task
def setup():
  install_native_packages()

  run("mkdir -p .pip/downloads")
  append(".pip/pip.conf", "[global]\ndownload-cache=~/.pip/downloads\n")

  require.directory("%s" % APPNAME)

  create_virtualenv()
  setup_nginx()
  register_on_supervisor()


def install_native_packages():
  sudo("apt-get update -qq")
  require.deb.packages(NATIVE_PACKAGES)


def create_virtualenv():
  sudo("chown -R %s:%s .pip" % (env.user, env.user))
  dir = make_absolute(env.target_dir)
  require.directory(dir)
  require.python.virtualenv(dir + "/env")
  sudo("chown -R %s:%s %s/env" % (env.user, env.user, dir))
  with virtualenv(dir + "/env"):
    require.python.package('tox')
    sudo("chown -R %s:%s %s/env" % (env.user, env.user, dir))
  sudo("chown -R %s:%s .pip" % (env.user, env.user))


def setup_nginx():
  require.nginx.server()

  directory = make_absolute(env.target_dir)
  require.nginx.site(env.SERVERNAME,
                     template_contents=NGINX_TPL,
                     port=PORT,
                     staticroot=directory)


@task
def register_on_supervisor():
  dir = make_absolute(env.target_dir)
  venv = dir + "/env"
  app = 'main:app'
  command = ("{venv}/bin/gunicorn -c '{dir}/gunicorn_settings.py' "
             "--bind 127.0.0.1:{port} '{app}'"
            ).format(venv=venv, dir=dir, port=PORT, app=app)

  require.supervisor.process(APPNAME,
                             command=command,
                             directory=dir,
                             user=env.user,
                             stdout_logfile=dir + '/server.log',
                             stderr_logfile=dir + '/error.log')

  supervisor.update_config()


#
# Real actions
#
@task
def push():
  """
  Pushes the source using rsync.

  TODO: change to git pulling.
  """
  #local("make clean")
  base_ssh = "ssh"
  if env.user == 'vagrant':
    base_ssh += " -i %s" % env.key_filename

  for host in env.hosts:
    ssh = base_ssh
    if host.rfind(':') > -1:
      host, port = host.rsplit(':', 1)
      ssh += " -p %s" % port

    local("rsync -avz -e '%s' %s %s . %s@%s:%s"
          % (ssh, RSYNC_OPTIONS, RSYNC_EXCLUDES,
             env.user, host, env.target_dir))


@task
def test():
  """
  Runs the test suite using tox in the testing dir.
  """
  directory = make_absolute(env.target_dir)
  venv = directory + "/env"
  with cd(directory):
    run("rm -rf *")
    with virtualenv(venv):
      run("cp -r ../src/* .")
      run("tox -e ALL")


@task(default=True)
def deploy():
  """
  Deploys the app and restarts the server.
  """
  directory = make_absolute(env.target_dir)
  venv = directory + "/env"
  with cd(directory):
    with virtualenv(venv):
      run("pip install -r deps.txt")

  if supervisor.process_status(env.app_name) == "RUNNING":
    supervisor.restart_process(env.app_name)


@task
def start():
  """
  Starts the server.
  """
  if supervisor.process_status(env.app_name) == "RUNNING":
    supervisor.restart_process(env.app_name)
  else:
    supervisor.start_process(env.app_name)


@task
def stop():
  """
  Stops the server.
  """
  supervisor.stop_process(env.app_name)


@task
def restart():
  stop()
  start()


@task
def golive():
  push()
  #test()
  deploy()
