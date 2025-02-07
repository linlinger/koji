#!/usr/bin/python3

import os
import shutil
import subprocess


def run(cmd, chdir=None):
    global logfd
    olddir = None
    if chdir:
        olddir = os.getcwd()
        os.chdir(chdir)

    workdir = os.getcwd()
    print(" # running `%s`" % ' '.join(cmd))
    print(" # workdir `%s`" % workdir)
    print(" # waiting ... (if error, retry 5 times)")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            close_fds=True)
    output, dummy = proc.communicate()
    ret = proc.returncode

    if olddir:
        os.chdir(olddir)
    if ret:
        msg = ' # failed! return code was %s, output:\n' % (ret)
        msg += '%s' % str(output.decode('utf8'))
        print(msg)
    else:
        msg = ' # success! return code was %s, output:\n' % (ret)
        msg += '%s' % str(output.decode('utf8'))
        print(msg)


def do_rocky():
    metadata_file = None
    src = {}
    if not os.path.exists('/ext/srpmproc'):
        print(" # Fatal error! /etc/srpmproc doesn't exists!")
        exit(1)
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.metadata'):
                metadata_file = file
    if not metadata_file:
        print(" # Fatal error! metadata file not found!")
        exit(1)
    with open(metadata_file) as f:
        metadata = f.readlines()
    for line in metadata:
        hashcode = line.split()[0]
        filepath = line.split()[1]
        src[filepath] = hashcode
        print(" # %s need download" % filepath)

    CDN_URL = "https://rocky-linux-sources-staging.a1.rockylinux.org"
    run(["/ext/srpmproc", "fetch", "--cdn-url=%s" % CDN_URL])
    download_success = True
    for path in src.keys():
        if not os.path.exists(path):
            print(" # Error! %s doesn't download success" % path)
            download_success = False
    if not download_success:
        CDN_URL = "https://sources.build.resf.org"
        run(["/ext/srpmproc", "fetch", "--cdn-url=%s" % CDN_URL])


def do_anolis():
    with open('download', 'r') as df:
        to_download = df.readlines()

    os.makedirs('SOURCES', exist_ok=True)
    os.makedirs('SPECS', exist_ok=True)

    for fd in os.listdir('.'):
        if '.git' == fd or 'SOURCES' == fd or 'SPECS' == fd:
            continue
        elif fd.endswith('.spec'):
            shutil.move(fd, 'SPECS')
        else:
            shutil.move(fd, 'SOURCES')

    for line in to_download:
        hashcode = line.split()[0]
        filename = line.split()[1]
        print("try download %s : %s" % (filename, hashcode))
        outpufile = "SOURCES/%s" % filename
        url = "http://build.openanolis.cn/kojifiles/upstream-source/%s.%s" % (filename, hashcode)
        run(["curl", "--retry", "5", "-o", outpufile, url])
    run(["find", "."])


"""
wget -O a.tar.xz http://build.openanolis.cn/kojifiles/upstream-source/a.tar.xz.6acca8f7109cc7ef465a5e3ee3254573    
"""


def do_openeuler():
    pass


def do_opencloudos():
    run(["/ext/opencloudos_getsrc.sh"])


if __name__ == "__main__":
    if not os.path.exists('.git/config'):
        print(" # Fatal error! current dir is not normal git repo")
        exit(1)
    print(" # find .git/config")

    with open('.git/config', 'r') as gitconfig:
        data = gitconfig.read()

    if 'gitee.com' in data:
        if 'anolis' in data and os.path.exists('download'):
            print(" # repo upstream is gitee.com openanolis community")
            do_anolis()
        if 'openeuler' in data:
            if os.path.exists('sources') or os.path.exists('SOURCES') or os.path.exists('source'):
                do_openeuler()
        if 'opencloudos' in data:
            do_opencloudos()
    elif 'git.centos.org' in data:
        print(" # repo upstream is git.centos.org")
        run(["/ext/centos_getsrc.sh"])
    elif 'git.rockylinux.org' in data:
        print(" # repo upstream is git.rockylinux.org")
        do_rocky()
    elif 'pagure.io' in data:
        print(" # repo upstream is pagure.io")
    else:
        print(" # Unkown upstream, be optimistic, maybe it's ok, keep running...")
    print(" # All done")
    exit(0)
