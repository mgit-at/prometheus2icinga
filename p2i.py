#!/usr/bin/python
#Disable: "Too many positional arguments for method call error":
#pylint: disable-msg=E1121

import sys, getopt
import urllib2
import json
import ast

class PromRequestError(Exception):
    def __init__(self, message, cause):
        if cause: 
            super(PromRequestError, self).__init__(
                message + u'caused by ' + repr(cause)
            )
            self.cause = cause
        else:
            super(PromRequestError, self).__init__(
                message
            )
            

class PromRequest(object):
    OK = 0
    WARNING = 1
    CRITICAL = 2
    UNKNOWN = 3

    def __init__(self, baseurl, alertname, labels, timeout=3, print_status_info=True):
        self.baseurl = baseurl
        self.alertname = alertname
        self.labels = labels
        self.timeout = timeout
        self.api_rules_endpoint = "api/v1/rules"
        self.api_alerts_endpoint = "api/v1/alerts"
        self.print_status_info = print_status_info

    def format_info(self, info):
        message = ""
        for line in info.splitlines():
            line = line.strip()
            message += line.strip("/") + "\n"
        return message

    def get_firing_alerts(self):
        try:
            alert_request = urllib2.urlopen(
                self.baseurl +
                self.api_alerts_endpoint,
                timeout=self.timeout
            ).read()
            alert_request = json.loads(alert_request)
        except urllib2.URLError as e:
            message = self.format_info(
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
                firingalerts.append([alert["labels"]["alertname"], alert["labels"]])
        except KeyError as e:
            message = self.format_info(
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
                self.api_rules_endpoint,
                timeout=self.timeout
            ).read()
            rules_request = json.loads(rules_request)
        except urllib2.URLError as e:
            message = self.format_info(
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
            message = self.format_info(
                """
                UNKNOWN
                API @ {api_rules_endpoint} might not be compatble.
                """.format(
                    api_rules_endpoint = self.api_rules_endpoint
                )
            )
            raise PromRequestError(message, e)

        return alertnames

    def get_firing_alerts_with_name(self):
        try:
            firingalerts = self.get_firing_alerts()
            relatedalerts = []

            if not firingalerts:
                return relatedalerts
    
            for firingalert in firingalerts:
                if firingalert[0] == self.alertname:
                    relatedalerts.append(firingalert)
        except PromRequestError as e:
            raise

        return relatedalerts

    def check_alert_status(self, throw_exception_if_unknown=True):
        try:
            if not self.alertname in self.get_alert_names():
                if not throw_exception_if_unknown:
                    return self.UNKNOWN # OUTDATED: TODO: Information gets lost here again *facepalm* change that!!!
                message = self.format_info(
                    """
                    Alert {alertname} does not exist.
                    """.format(
                        alertname = self.alertname
                    )
                )
                raise PromRequestError(message, None)
                
            firingalerts = self.get_firing_alerts_with_name()
            
            self.check_alert_logic(self, firingalerts)

        except PromRequestError as e:
            if not throw_exception_if_unknown:
                return self.UNKNOWN # OUTDATED: TODO: THIS WAY THE CAUSE OF THE EXCEPTION GETS LOST CHAGE THAT!!!
            raise e

        return self.OK

    def check_alert_logic(self, firingalerts):
        if not firingalerts:
                if self.print_status_info:
                    print("OK: 0")
                return self.OK
            
        for i in range(2):
            for firingalert in firingalerts:
                if self.labels.viewitems() <= firingalert[1].viewitems():
                    try:
                        if i == 0:
                            if firingalert[1]["severity"] in ("crit", "critical"):
                                if self.print_status_info:
                                    print("CRITICAL: 2")
                                return self.CRITICAL
                        if i == 1:
                            if firingalert[1]["severity"] in ("warn", "warning"): #unsafe keyerror if not severity; make this configurable
                                if self.print_status_info:
                                    print("WARNING: 1")
                                return self.WARNING
                    except KeyError as e:
                        message = self.format_info(
                            """
                            Alert {alertname} has no label {missinglabel}.
                            "{missinglabel}" is used to determine the severity of the alert.
                            """.format(
                                alertname = self.alertname,
                                missinglabel = "severity"
                            )
                        )
                        raise PromRequestError(message, e)


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
            /    -l, --labels      The labels you want the alert to be
            /                      checked for. (e.g. "{{'instance':'localhost:9090'}}")
            /    -t, --timeout     How long schould be waited in case that
            /                      Prometheus does not respond before returning
            /                      UNKNOWN (RC=3). Default timeout = {default_timeout}
            /                      (timeout in seconds)
            /    -s, --statusinfo  Print Status of Alert in adition to exiting with the 
            /                      corresponding RC. Default = True. (True/False)
            /
            """.format(scriptname = __file__, api_endpoint = "api/v1/*", default_timeout = 3)

    def print_usage():
        for line in usage.splitlines():
            line = line.strip()
            print line.strip("/")

    try:
       opts, args = getopt.getopt(argv,"hb:a:l:t:s:",["baseurl=","alertname=","labels=","timeout=", "statusinfo="])
    except getopt.GetoptError:
       print_usage()
       sys.exit(3)

    baseurl = None
    alertname = None
    labels = None
    timeout = 3.0
    statusinfo = None

    for opt, arg in opts:
       if opt == '-h':
            print_usage()
            sys.exit(3)
       elif opt in ("-b", "--baseurl"):
            baseurl = arg
       elif opt in ("-a", "--alertname"):
            alertname = arg
       elif opt in ("-l", "--labels"):
            labels = arg
       elif opt in ("-t", "--timeout"):
            try:
                timeout = float(arg)
            except ValueError as e:
                print "Timeout must be an Int or Float\n\n"
                print_usage()
                sys.exit(3)
       elif opt in ("-s", "--statusinfo"):
            if statusinfo == "True":
                statusinfo = True
                break
            if statusinfo == "False":
                statusinfo = False
                break
            print "Parameter -s, --statusinfo must be True or False. Default = True."
            print_usage()
            sys.exit(3)

    if not statusinfo:
        statusinfo = True

    if not baseurl and not alertname and not labels:
        print_usage()
        sys.exit(3)

    if not baseurl or not alertname or not labels:
        print "The arguments baseurl, alertname and labels must be specified."
        print_usage()
        sys.exit(3)

    if not baseurl.endswith("/"):
        baseurl += "/"

    try:
        labels = ast.literal_eval(labels)
    except ValueError:
        print "Please specify labels like this:    -l \"{'instance': 'localhost:9090', 'example-label': 'blafoo'}\""
        sys.exit(3)
    except SyntaxError:
        print "Please use single quotes for labels. e.g.    -l \"{'instance': 'localhost:9090', 'example-label': 'blafoo'}\""
        sys.exit(3)

    return baseurl, alertname, labels, timeout, statusinfo

def main(argv):
    args = get_args(argv)
    prom_request = PromRequest(args[0], args[1], args[2], args[3], args[4])
    STATUS = 0
    try:
        STATUS = prom_request.check_alert_status()
    except PromRequestError as e:
        print e
        STATUS = 3
    return STATUS

if __name__ == "__main__":
    import doctest
    doctest.testmod()
    sys.exit(main(sys.argv[1:]))