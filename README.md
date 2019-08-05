# Prometheus2Icinga

Usage: p2i.py [OPTIONS]

Description:

    Script for integrating Prometheus alerts into Icinga/Nagios.
    This script will connect to a Prometheus instance via its
    API under api/v1/* and retrieve the status of a specifc
    alert for a specific instance. In order for this script to work
    you have to set a label named severity to either 'warn'/'warning'
    for a return code of 1 (warning) or to 'crit'/'critical' for a
    return code of 2 (critical). If the status of the alert is unknown
    this script will return 3 (unknown) and if the alert is not firing
    it will return 0 (ok). For more information visit:
    https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/3/en/pluginapi.html

Options:

    -b, --baseurl     Base-Url of the Prometheus instance.
                      (e.g. "http://localhost:9090/")
                      Prometheus API endpoints will be
                      automatically used.
    -a, --alertname   Name of the alert you want to check.
    -l, --labels      The labels you want the alert to be
                      checked for. (e.g. '{"instance":"localhost:9090"}')
    -t, --timeout     How long should be waited in case that
                      Prometheus does not respond before returning
                      UNKNOWN (RC=3). Default timeout = 60.0
                      (timeout in seconds)
    -s, --statusinfo  Print status of an alert in addition to exiting with
                      the corresponding RC. Default = True. (True/False)
    --ignore-ssl      THIS IS NOT SAFE: this is only for testing purposes
                      and should never be used in any kind of production
                      envoirement. If this option is set this script won't
                      validate certificates.
    --netrc-path      Path to netrc file. If not specified a file named
                      .netrc is expected in the user's home directory.
    --basic-auth      If specified this script will try to authenticate
                      itself via basic auth with the credentials in the
                      .netrc file. The netrc "machine" attribute must be
                      set to "prometheus"

## How to install

In order to get it to work you just have to clone this Repository

```git clone git@github.com:mgit-at/prometheus2icinga.git```

You can either use this script manually to retrieve the status of an alert or let Icinga call it\
instead. If you want to use this script with Icinga you have to move p2i into the Icinga plugins folder.

### Integration into Prometheus

The following is an example of a prometheus alert that works with this script:
```
groups:
- name: example
  rules:
  - alert: HighRequestLatency
    expr: job:request_latency_seconds:mean5m{job="myjob"} > 0.5
    for: 10m
    labels:
      severity: critical
    annotations:
      summary: High request latency
```

Notice that `severity` is set to `critical`.

The only thing you have to do to get your existing alerts to work with p2i is to\
add a severity label to your alerts that is set to either `critical`/`crit` or `warning`/`warn`\
depending on how important the alert is. An alert set to `critical` will result in a returncode\
of 2 while an alert set to `warning` will result in a returncode of 1.\
An example p2i call requesting the status of this alert would look something like this:\
`python p2i.py --alertname 'HighRequestLatency' --baseurl 'http://localhost/prometheus/' --labels '{"instance":"localhost"}'`

### Integration into Icinga2

In order to integrate this script into Icinga you'll have to add p2i to the plugins folder of your\
Icinga2, the location of this folder varys across operating systems so please refer to the Icinga\
Documentation for the exact location. The actual integration into Icinga2 varys widely from setup\
to setup. If you're using Icinga2 in combination with Icinga Director you'll have to create a new\
command in the web-frontend. With other setups you might need to add the neccessary configuration\
Objects on the Icinga Master/Satellite.

### Basic auth support

Prometheus2Icinga has basic auth support. It is highly recommended that you use this feature\
instead of exposing your prometheus Instance to the whole internet when using this script\
across multiple servers. In order to use this feature you'll have to provide the credentials\
for basic auth in a so called netrc file. To do this you can either create a file named `.netrc`\
in your users home directory or you can specify a custom file path via the option:\
```--netrc-path "/path/to/example_netrc_file.netrc"``` 

Here is an example of a netrc file:\
```machine prometheus login YOUR_USER password YOUR_PASSWORD```

Please note that machine *has* to be set to *`prometheus`* for this script.

