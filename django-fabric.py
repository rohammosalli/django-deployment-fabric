
from __future__ import with_statement # needed for python 2.5
from fabric.api import *

# globals
env.project_name = 'project_name'
env.use_roham = False # django-roham app 

# environments

def localhost():
    "Use the local virtual server"
    env.hosts = ['localhost']
    env.user = 'username'
    env.path = '/home/%(user)s/workspace/%(project_name)s' % env
    env.virtualhost_path = env.path

def webserver():
    "Use the actual webserver"
    env.hosts = ['www.roham.com] # change whatever you want 
    env.user = 'username'
    env.path = '/var/www/%(project_name)s' % env
    env.virtualhost_path = env.path
    
# tasks

def test():
    "Run the test"
    result = local("cd %(path)s; python manage.py test" % env) #, fail="abort")
    
    
def setup():
    """
    Setup a fresh virtualenv
    """
    require('hosts', provided_by=[localhost,webserver])
    require('path')
    sudo('aptitude install -y python-setuptools')
    sudo('easy_install pip')
    sudo('pip install virtualenv')
    sudo('aptitude install -y apache2-threaded')
    sudo('aptitude install -y libapache2-mod-wsgi') 
    
    sudo('cd /etc/apache2/sites-available/; a2dissite default;', pty=True)
    sudo('mkdir -p %(path)s; chown %(user)s:%(user)s %(path)s;' % env, pty=True)
    run('ln -s %(path)s www;' % env, pty=True) # symlink web dir in home
    with cd(env.path):
        run('virtualenv .;' % env, pty=True)
        run('mkdir logs; chmod a+w logs; mkdir releases; mkdir shared; mkdir packages;' % env, pty=True)
        if env.use_photologue: run('mkdir photologue');
        run('cd releases; ln -s . current; ln -s . previous;', pty=True)
    deploy()
    
def deploy():
    """
    Deploy the latest version of the site to the servers
    """
    require('hosts', provided_by=[localhost,webserver])
    require('path')
    import time
    env.release = time.strftime('%Y%m%d%H%M%S')
    upload_tar_from_git()
    install_requirements()
    install_site()
    symlink_current_release()
    migrate()
    restart_webserver()
    
def deploy_version(version):
    "Specify a specific version to be made live"
    require('hosts', provided_by=[localhost,webserver])
    require('path')
    env.version = version
    with cd(env.path):
        run('rm releases/previous; mv releases/current releases/previous;', pty=True)
        run('ln -s %(version)s releases/current' % env, pty=True)
    restart_webserver()
    
def rollback():
    """
    Limited rollback capability. Simple loads the previously current
    version of the code. Rolling back again will swap between the two.
    """
    require('hosts', provided_by=[localhost,webserver])
    require('path')
    with cd(env.path):
        run('mv releases/current releases/_previous;', pty=True)
        run('mv releases/previous releases/current;', pty=True)
        run('mv releases/_previous releases/previous;', pty=True)
    restart_webserver()    
    


def upload_tar_from_git():
    "Create an archive from the current Git master branch and upload it"
    require('release', provided_by=[deploy, setup])
    local('git archive --format=tar master | gzip > %(release)s.tar.gz' % env)
    run('mkdir -p %(path)s/releases/%(release)s' % env, pty=True)
    put('%(release)s.tar.gz' % env, '%(path)s/packages/' % env)
    run('cd %(path)s/releases/%(release)s && tar zxf ../../packages/%(release)s.tar.gz' % env, pty=True)
    local('rm %(release)s.tar.gz' % env)
    
def install_site():
    "Add the virtualhost file to apache"
    require('release', provided_by=[deploy, setup])
    #sudo('cd %(path)s/releases/%(release)s; cp %(project_name)s%(virtualhost_path)s%(project_name)s /etc/apache2/sites-available/' % env)
    sudo('cd %(path)s/releases/%(release)s; cp vhost.conf /etc/apache2/sites-available/%(project_name)s' % env)
    sudo('cd /etc/apache2/sites-available/; a2ensite %(project_name)s' % env, pty=True) 
    
def install_requirements():
    "Install the required packages from the requirements file using pip"
    require('release', provided_by=[deploy, setup])
    run('cd %(path)s; pip install -E . -r ./releases/%(release)s/requirements.txt' % env, pty=True)
    
def symlink_current_release():
    "Symlink our current release"
    require('release', provided_by=[deploy, setup])
    with cd(env.path):
        run('rm releases/previous; mv releases/current releases/previous;')
        run('ln -s %(release)s releases/current' % env)
        if env.use_photologue:
            run('cd releases/current/%(project_name)s/static; rm -rf photologue; ln -s %(path)s/photologue;' % env, pty=True)
    
def migrate():
    "Update the database"
    require('project_name')
    run('cd %(path)s/releases/current/%(project_name)s;  ../../../bin/python manage.py syncdb --noinput' % env, pty=True)
    
def restart_webserver():
    "Restart the web server"
sudo('/etc/init.d/apache2 reload', pty=True)
