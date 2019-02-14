#!/usr/bin/env python3
import os
import traceback
import importlib
import imp
import types
import subprocess
import pwd
import sys
import datetime
import time
import fcntl
from optparse import OptionParser


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def parse_config_modules(conf1, conf2):
    obj = types.SimpleNamespace()
    attributes1 = [attr for attr in dir(conf1) if not attr.startswith("_") and not attr.endswith("_")]
    attributes2 = [attr for attr in dir(conf2) if not attr.startswith("_") and not attr.endswith("_")]
    for attr in attributes1:
        setattr(obj, attr, getattr(conf1, attr))

    for attr in attributes2:
        setattr(obj, attr, getattr(conf2, attr))

    return obj


def get_uid_gid(username: str) -> tuple:
    pw_record = pwd.getpwnam(username)
    return (pw_record.pw_uid, pw_record.pw_gid)


def run_command_as_user(username, working_directory, *args) -> tuple:
    def demote(uid, gid):
        def result():
            try:
                os.setgid(gid)
                os.setuid(uid)
            except PermissionError:
                eprint("You do not have permissions to login as user {}".format(username))
                os._exit(1)
        return result

    pw_record = pwd.getpwnam(username)
    env = os.environ.copy()
    env["HOME"] = pw_record.pw_dir
    env["LOGNAME"] = pw_record.pw_name
    env["PWD"] = working_directory
    env["USER"] = pw_record.pw_name
    process = subprocess.Popen(
            args,
            preexec_fn=demote(pw_record.pw_uid, pw_record.pw_gid),
            cwd=working_directory,
            env=env,
    )
    return (process.wait(), )


def get_dump_files(dir_path):
    files = [
            (
                os.path.join(dir_path, f), 
                os.stat(os.path.join(dir_path, f)).st_size,
                *f.split("__")[::-1],
            )
            for f in os.listdir(dir_path)
            if os.path.isfile(os.path.join(dir_path, f)) and f.endswith(".dump")
    ]
    files.sort(key=lambda x: int(x[3]))
    return files


def clean_dir(dir_path, config):
    print("cleaning {} ...".format(dir_path))
    files = get_dump_files(dir_path)
    while files and len(files) > config.files_limiter:
        os.remove(files[0][0])
        del files[0]

    allowed_size_bytes = config.size_limiter_gb * 1024 * 1024 * 1024

    while files and sum(f[1] for f in files) > allowed_size_bytes:
        os.remove(files[0][0])
        del files[0]


def process_config(default_config_path, config_path: str):
    print("processing", config_path, "...")
    default_config_module = imp.load_source("default_config", default_config_path)
    config_module = imp.load_source("config", config_path)

    config = parse_config_modules(default_config_module, config_module)
    dir_path = os.path.join(config.dumps_dir, config.database_name)
    os.makedirs(dir_path, mode=0o777, exist_ok=True)
    uid, gid = get_uid_gid(config.run_as_user)
    os.chown(dir_path, uid, gid)

    # check dir
    timestamp = int(time.time())
    str_date = datetime.datetime.fromtimestamp(timestamp).strftime("%Y_%B_%d_%H:%M:%S")
    dump_file_name = config.file_name_prefix + "{}__{}__{}__pg.dump.unfinished".format(
        config.database_name,
        str_date,
        timestamp,
    )
    finished_dump_file_name = config.file_name_prefix + "{}__{}__{}__pg.dump".format(
        config.database_name,
        str_date,
        timestamp,
    )
    dump_files = get_dump_files(dir_path)
    if dump_files and int(dump_files[-1][3]) + config.dumping_period_seconds > timestamp:
        print("skipping", config_path, "...")
        return

    dump_file_path = os.path.join(dir_path, dump_file_name)
    finished_dump_file_path = os.path.join(dir_path, finished_dump_file_name)

    args = ["pg_dump", "-Fc", "--file="+dump_file_path, config.database_name]

    run_command_as_user(config.run_as_user, dir_path, *args)
    # rename to be sure that dump finished sucessfully
    os.rename(dump_file_path, finished_dump_file_path)

    clean_dir(dir_path, config)


def main():
    parser = OptionParser()
    parser.add_option("-c", "--configs-dir", dest="configs_dir", help="configs directory")
    options, args = parser.parse_args()

    configs_dir = ""
    if options.configs_dir:
        configs_dir = options.configs_dir

    if not configs_dir:
        raise Exception("use -c option")

    for config_filename in os.listdir(configs_dir):
        config_path = os.path.join(configs_dir, config_filename)
        if config_filename != "default.conf.py" and os.path.isfile(config_path) and config_path.endswith(".conf.py") :
            try:
                process_config(os.path.join(configs_dir, "default.conf.py"), config_path)
            except BaseException:
                traceback.print_exc()


if __name__ == "__main__":
    pid_file = "dump_it.pid"
    fp = open(pid_file, "w")
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        main()
    except IOError:
        print("another instance is already running")
        sys.exit(1)

