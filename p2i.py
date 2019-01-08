#!/usr/bin/python

import sys, getopt
import urllib2
import json

OK = 0
WARNING = 1
CRITICAL = 2
UNKNOWN = 3

def get_args(argv):

    usage = """
            //   _______    ______   ______
            //  /       \  /      \ /      |
            //  $$$$$$$  |/$$$$$$  |$$$$$$/
            //  $$ |__$$ |$$____$$ |  $$ |
            //  $$    $$/  /    $$/   $$ |
            //  $$$$$$$/  /$$$$$$/    $$ |
            //  $$ |      $$ |_____  _$$ |_
            //  $$ |      $$       |/ $$   |
            //  $$/       $$$$$$$$/ $$$$$$/


            Usage: {scriptname} [OPTIONS]

            Description:

            /    Script for integrating Prometheus alerts into Icinga/Nagios.
            /    This Script will connect to a Prometheus instance via its
            /    API under {api_endpoint} and retrieve the status of a specifc
            /    alert for a specific instance. For more Information visit:
            /    https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/3/en/pluginapi.html

            Options:

            /    -b, --baseurl     Base-Url of the Prometheus instance.
            /                      (e.g. "http://localhost:9090/")
            /                      Prometheus API endpoints will be
            /                      automatically used.
            /    -a, --alertname   Name of the alert you want to check.
            /    -i, --instance    The instance you want the alert to be
            /                      checked for. (e.g. "localhost:9090")
            /    -t, --timeout     How long schould be waited in case that
            /                      Prometheus does not respond before returning
            /                      UNKNOWN (RC=3). Default timeout = {default_timeout}
            /                      (timeout in seconds)
            /
            """.format(scriptname = __file__, api_endpoint = "api/v1/*", default_timeout = 3)

    def print_usage():
        for line in usage.splitlines():
            line = line.strip()
            print line.strip("/")

    try:
       opts, args = getopt.getopt(argv,"hb:a:i:t:",["baseurl=","alertname=","instance=","timeout="])
    except getopt.GetoptError:
       print_usage()
       sys.exit(UNKNOWN)

    baseurl = None
    alertname = None
    instance = None
    timeout = 3.0

    for opt, arg in opts:
       if opt == '-h':
            print_usage()
            sys.exit(3)
       elif opt in ("-b", "--baseurl"):
            baseurl = arg
       elif opt in ("-a", "--alertname"):
            alertname = arg
       elif opt in ("-i", "--instance"):
            instance = arg
       elif opt in ("-t", "--timeout"):
            try:
                timeout = float(arg)
            except ValueError as e:
                print "Timeout must be an Int or Float\n\n"
                print_usage()
                sys.exit(UNKNOWN)

    if not baseurl and not alertname and not instance:
        print_usage()
        sys.exit(UNKNOWN)

    if not baseurl or not alertname or not instance:
        print "The arguments baseurl, alertname and instance must be specified."
        print_usage()
        sys.exit(UNKNOWN)

    if not baseurl.endswith("/"):
        baseurl += "/"

    return baseurl, alertname, instance, timeout

def get_alert_names(baseurl, api_rules_endpoint, timeout):
    try:
        rules_request = urllib2.urlopen(baseurl + api_rules_endpoint, timeout=timeout).read()
        rules_request = json.loads(rules_request)
    except urllib2.URLError as e:
        print "Service @ " +  api_rules_endpoint + " not reachable."
        print "Are you sure Prometheus is up and running @ " + baseurl + api_rules_endpoint + " ?"
        print e
        sys.exit(UNKNOWN)

    alertnames = []
    try:
        groups = rules_request["data"]["groups"]
        for group in groups:
            rules = group["rules"]
            for rule in rules:
                if rule["type"] == "alerting":
                    alertnames.append(rule["name"])
    except KeyError as e:
        print e
        sys.exit(UNKNOWN)

    return alertnames

def get_firing_alerts(baseurl, api_alerts_endpoint, instance, timeout):
    try:
       alert_request = urllib2.urlopen(baseurl + api_alerts_endpoint, timeout=timeout).read()
       alert_request = json.loads(alert_request)
    except urllib2.URLError as e:
        print "Service @ " +  api_alerts_endpoint + " not reachable."
        print "Are you sure Prometheus is up and running @ " + baseurl + api_alerts_endpoint + " ?"
        sys.exit(UNKNOWN)

    firingalerts = []

    try:
        alerts = alert_request["data"]["alerts"]
        for alert in alerts:
            if alert["labels"]["instance"] == instance:
                firingalerts.append(alert["labels"]["alertname"])
    except KeyError as e:
        print "UNKNOWN"
        print "Api @ " + api_alerts_endpoint + " might not be compatible."
        print e
        sys.exit(UNKNOWN)

    return firingalerts

def check_alert_status(alertname, alertnames, firingalerts):
    if not alertname + "_warn" in alertnames or not alertname + "_crit" in alertnames:
        print "Alert(s) " + alertname + "_warn" + " and/or " + alertname + "_crit" + " do not exist."
        return UNKNOWN

    if alertname + "_crit" in firingalerts:
        return CRITICAL

    if alertname + "_warn" in firingalerts:
        return WARNING

    return OK

def main(argv):
    args = get_args(argv)
    baseurl = args[0]
    alertname = args[1]
    instance = args[2]
    timeout = args[3]

    alertnames = get_alert_names(baseurl, "api/v1/rules", timeout)
    firingalerts = get_firing_alerts(baseurl, "api/v1/alerts", instance, timeout)

    return check_alert_status(alertname, alertnames, firingalerts)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
