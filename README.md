# Prometheus2Icinga

Usage: p2i.py [OPTIONS]

Description:

    Script for integrating Prometheus alerts into Icinga/Nagios.
    This Script will connect to a Prometheus instance via its
    API under api/v1/* and retrieve the status of a specifc
    alert for a specific instance. For more Information visit:
    https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/3/en/pluginapi.html

Options:

    -b, --baseurl     Base-Url of the Prometheus instance.
                      (e.g. "http://localhost:9090/")
                      Prometheus API endpoints will be
                      automatically used.
    -a, --alertname   Name of the alert you want to check.
    -l, --labels      The labels you want the alert to be
                      checked for. (e.g. "{'instance':'localhost:9090'}")
    -t, --timeout     How long schould be waited in case that
                      Prometheus does not respond before returning
                      UNKNOWN (RC=3). Default timeout = 3
                      (timeout in seconds)
    -s, --statusinfo  Print Status of Alert in adition to exiting with the
                      corresponding RC. Default = True. (True/False)

