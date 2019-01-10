#!/usr/bin/python

import sys, getopt
import urllib2
import json

class PromRequestError(Exception):
    def __init__(self, message, cause):
        super(PromRequestError, self).__init__(
            message + u'caused by ' + repr(cause)
        )
        self.cause = cause

class PromRequest(object):
    OK = 0
    WARNING = 1
    CRITICAL = 2
    UNKNOWN = 3

    def __init__(self, baseurl, alertname, labels, timeout):
        self.baseurl = baseurl
        self.alertname = alertname
        self.labels = labels
        self.timeout = timeout
        self.api_rules_endpoint = "api/v1/rules"
        self.api_alerts_endpoint = "api/v1/alerts"

    def format_info(info):
        message = ""
        for line in info.splitlines:
            line = line.strip
            message += line.strip("/") + "\n" # TODO: check if this os formatting correct
        return message

    def get_firing_alerts(self):
        try:
            alert_request = urllib2.urlopen(
                self.baseurl +
                api_alerts_endpoint,
                timeout=self.timeout
            ).read()
            alert_request = json.loads(alert_request)
        except urllib2.URLError as e:
            message = format_info(
                """
                Service @ {api_alerts_endpoint} not reachable.
                Are you sure Prometheus is up and running @ {baseurl}{api_alerts_endpoint}?
                """.format(
                    api_alerts_endpoint = self.api_alerts_endpoint,
                    baseurl = self.baseurl 
                )
            )
            raise PromRequestError(message, e)

        firingalerts = []

        try:
            alerts = alert_request["data"]["alerts"]
            for alert in alerts:
                if alert["labels"]["instance"] == instance:
                    firingalerts.append(alert["labels"]["alertname"])
        except KeyError as e:
            message = format_info(
                """
                UNKNOWN
                API @ {api_alerts_endpoint} might not be compatble.
                """.format(
                    api_alerts_endpoint = self.api_alerts_endpoint
                )
            )
            raise PromRequestError(message, e)

        return firingalerts

    def get_alert_names(self):
        try:
            rules_request = urllib2.urlopen(
                self.baseurl +
                api_rules_endpoint,
                timeout=self.timeout
            ).read()
            rules_request = json.loads(rules_request)
        except urllib2.URLError as e:
            message = format_info(
                """
                Service @ {api_rules_endpoint} not reachable.
                Are you sure Prometheus is up and running @ {baseurl}{api_alerts_endpoint}?
                """.format(
                    api_rules_endpoint = self.api_alerts_endpoint,
                    baseurl = self.baseurl
                )
            )
            raise PromRequestError(message, e)

        alertnames = []
        try:
            groups = rules_request["data"]["groups"]
            for group in groups:
                rules = group["rules"]
                for rule in rules:
                    if rule["type"] == "alerting":
                        alertnames.append(rule["name"])
        except KeyError as e:
            message = format_info(
                """
                UNKNOWN
                API @ {api_rules_endpoint} might not be compatble.
                """.format(
                    api_rules_endpoint = self.api_rules_endpoint
                )
            )
            raise PromRequestError(message, e)

        return alertnames

    def alert_exists(self, alertname):
        return alername in self.get_alert_names(self) # TODO: Should I capture Exceptions here? ~No? What happens if this gets called outside of this class and does not get handled? RC? 

    def check_alert_status(self, alertname, throw_exception_if_unknown=True):
        try:
            if not self.alert_exists(self, alertname):
                if not throw_exception_if_unknown:
                    return UNKNOWN # TODO: Information gets lost here again *facepalm* change that!!!
                message = self.format_info(
                    """
                    Alert {alertname} does not exist.
                    """.format(
                        alertname = alertname
                    )
                )
                raise PromRequestError(message)

         # TODO: WARN CRIT    
            

        except PromRequestError as e:
            if not throw_exception_if_unknown:
                return UNKNOWN # TODO: THIS WAY THE CAUSE OF THE EXCEPTION GETS LOST CHAGE THAT!!!

        return OK

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

def main(argv):
    args = get_args(argv)
    prom_request = new PromRequest(args[0], args[1], args[2], args[3])

    return prom_request.check_alert_status()

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

   # if not alertname + "_warn" in alertnames or not alertname + "_crit" in alertnames:
   #     print "Alert(s) " + alertname + "_warn" + " and/or " + alertname + "_crit" + " do not exist."
   #     return UNKNOWN

   # if alertname + "_crit" in firingalerts:
   #     return CRITICAL

   # if alertname + "_warn" in firingalerts:
   #     return WARNING

   # return OK