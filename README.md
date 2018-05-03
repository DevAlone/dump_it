# dump_it

Simple tool for easy database dumping(only postgresql is supported yet).

## How to?

* Clone this repository

`git clone https://github.com/DevAlone/dump_it`

* Go to `dump_it` dir

`cd dump_it`

* Create configs

```bash
cp default.conf.py.example default.conf.py
cp example.conf.py.example example.conf.py
```

Default config is config with global settings, each of which can be overridden in config for database. Example of config for database is test.conf.py.example. You can create as many configs as many databases you have

* Create cron rule

`sudo crontab -e`

```
* * * * * PATH_TO_REPOSITORY/dump.py -c PATH_TO_REPOSITORY > /var/log/dump_it.stdout.log 2> /var/log/dump_it.stderr.log
```

And don't forget to change PATH_TO_REPOSITORY to actual path of where you cloned it. So program will be running every minute, getting configs from repository dir and writing logs to /var/log/dump_it.stdout.log and /var/log/dump_it.stderr.log

Happy dumping!
