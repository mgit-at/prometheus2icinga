#!/usr/bin/python
#Disable: "Too many positional arguments for method call error":
#pylint: disable-msg=E1121

import sys, getopt
import urllib2, base64
import json
import ssl
import netrc

class PromRequestError(Exception):
    def __init__(self, message, cause):
        if cause: 
            super(PromRequestError, self).__init__(
                message + u' caused by ' + repr(cause)
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

    def __init__(self, baseurl, alertname, labels, timeout=60.0, print_status_info=True, ignore_cert=False, basic_auth=False, netrc_path=None):
        self.baseurl = baseurl
        self.alertname = alertname
        self.labels = labels
        self.timeout = timeout
        self.api_rules_endpoint = "api/v1/rules"
        self.api_alerts_endpoint = "api/v1/alerts"
        self.print_status_info = print_status_info
        self.ignore_cert = ignore_cert
        self.basic_auth = basic_auth
        self.netrc_path = netrc_path

        if ignore_cert:
            self.ctx = ssl.create_default_context()
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

        if basic_auth:
            # netrc support here
            if self.netrc_path:
                netRc = netrc.netrc(self.netrc_path)
            else:
                netRc = netrc.netrc()
            authTokens = netRc.authenticators("prometheus")
            self.base64auth = base64.b64encode('%s:%s' % (authTokens[0], authTokens[2]))

    def format_info(self, info):
        message = ""
        for line in info.splitlines():
            line = line.strip()
            message += line.strip("/") + "\n"
        return message

    def get_firing_alerts(self):
        try:
            a_request = urllib2.Request(
                self.baseurl +
                self.api_alerts_endpoint
            )
            if self.basic_auth:
                a_request.add_header("Authorization", "Basic %s" % self.base64auth)
            
            if self.ignore_cert:
                alert_request = urllib2.urlopen(
                    a_request,
                    timeout=self.timeout,
                    context=self.ctx
                ).read()
            else:
                alert_request = urllib2.urlopen(
                    a_request,
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

        except ssl.CertificateError as e:
            raise PromRequestError(e.message, e)

        firingalerts = []

        try:
            alerts = alert_request["data"]["alerts"]
            for alert in alerts:
                if "annotations" in alert:
                    if "summary" in alert["annotations"]:
                        firingalerts.append([alert["labels"]["alertname"], alert["labels"], alert["annotations"]["summary"]])
                else:
                    firingalerts.append([alert["labels"]["alertname"], alert["labels"], "No Summary available"])
        except KeyError as e:
            message = self.format_info(
                """
                UNKNOWN
                API @ {api_alerts_endpoint} might not be compatible.
                """.format(
                    api_alerts_endpoint = self.api_alerts_endpoint
                )
            )
            raise PromRequestError(message, e)

        return firingalerts

    def get_alert_names(self):
        try:
            r_request = urllib2.Request(
                self.baseurl +
                self.api_rules_endpoint
            )
            if self.basic_auth:
                r_request.add_header("Authorization", "Basic %s" % self.base64auth)
            
            if self.ignore_cert:
                rules_request = urllib2.urlopen(
                    r_request,
                    timeout=self.timeout,
                    context=self.ctx
                ).read()
            else:
                rules_request = urllib2.urlopen(
                    r_request,
                    timeout=self.timeout
                ).read()

            rules_request = json.loads(rules_request)

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
        
        except ssl.CertificateError as e:
            raise PromRequestError(e.message, e)

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
                    return self.UNKNOWN
                message = self.format_info(
                    """
                    Alert {alertname} does not exist.
                    """.format(
                        alertname = self.alertname
                    )
                )
                raise PromRequestError(message, None)
                
            firingalerts = self.get_firing_alerts_with_name()
            
            return self.check_alert_logic(firingalerts)

        except PromRequestError as e:
            if not throw_exception_if_unknown:
                return self.UNKNOWN
            raise e

        return self.OK

    def check_alert_logic(self, firingalerts):
        if not firingalerts:
                if self.print_status_info:
                    print("OK: 0")
                return self.OK
            
        for i in range(2):
            for firingalert in firingalerts:
                if self.labels.viewitems() <= firingalert[1].viewitems(): # firingalert = [alertname, [labels], summary]
                    try:
                        if i == 0:
                            if firingalert[1]["severity"] in ("crit", "critical", "page"):
                                if self.print_status_info:
                                    print("CRITICAL: 2\n")
                                    print("Summary: %s" % (firingalert[2]))
                                return self.CRITICAL
                        if i == 1:
                            if firingalert[1]["severity"] in ("warn", "warning"): #unsafe keyerror if not severity; make this configurable
                                if self.print_status_info:
                                    print("WARNING: 1\n")
                                    print("Summary: %s" % (firingalert[2]))
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
            /    This script will connect to a Prometheus instance via its
            /    API under {api_endpoint} and retrieve the status of a specifc
            /    alert for a specific instance. In order for this script to work
            /    you have to set a label named severity to either {severity_warn}
            /    for a return code of 1 (warning) or to {severity_crit} for a
            /    return code of 2 (critical). If the status of the alert is unknown
            /    this script will return 3 (unknown) and if the alert is not firing
            /    it will return 0 (ok). For more information visit:
            /    https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/3/en/pluginapi.html

            Options:

            /    -b, --baseurl     Base-Url of the Prometheus instance.
            /                      (e.g. "http://localhost:9090/")
            /                      Prometheus API endpoints will be
            /                      automatically used.
            /    -a, --alertname   Name of the alert you want to check.
            /    -l, --labels      The labels you want the alert to be
            /                      checked for. (e.g. '{{"instance":"localhost:9090"}}')
            /    -t, --timeout     How long should be waited in case that
            /                      Prometheus does not respond before returning
            /                      UNKNOWN (RC=3). Default timeout = {default_timeout}
            /                      (timeout in seconds)
            /    -s, --statusinfo  Print status of an alert in addition to exiting with
            /                      the corresponding RC. Default = True. (True/False)
            /    --ignore-ssl      THIS IS NOT SAFE: this is only for testing purposes
            /                      and should never be used in any kind of production
            /                      envoirement. If this option is set this script won't
            /                      validate certificates.
            /    --netrc-path      Path to netrc file. If not specified a file named 
            /                      .netrc is expected in the user's home directory.
            /    --basic-auth      If specified this script will try to authenticate
            /                      itself via basic auth with the credentials in the
            /                      .netrc file. The netrc "machine" attribute must be
            /                      set to "prometheus"
            /
            """.format(
                    scriptname = __file__,
                    api_endpoint = "api/v1/*",
                    severity_warn = "'warn'/'warning'",
                    severity_crit = "'crit'/'critical'",
                    default_timeout = 60.0
            )

    def print_usage():
        for line in usage.splitlines():
            line = line.strip()
            print line.strip("/")

    try:
       opts, args = getopt.getopt(argv,"hb:a:l:t:s:",["baseurl=","alertname=","labels=","timeout=", "statusinfo=", "ignore-ssl", "basic-auth", "netrc-path="])
    except getopt.GetoptError:
       print_usage()
       sys.exit(3)

    baseurl = None
    alertname = None
    labels = None
    timeout = 60.0
    statusinfo = None
    ignore_cert = False
    basic_auth = False
    netrc_path = None

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
                print "Timeout must be an int or float\n\n"
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
        elif opt in ("--ignore-ssl"):
            ignore_cert = True
        elif opt in ("--netrc-path"):
            netrc_path = arg
        elif opt in ("--basic-auth"):
            basic_auth = True

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
        labels = json.loads(labels)
    except ValueError:
        print "Please specify labels like this:    -l '{\"instance\": \"localhost:9090\", \"example-label\": \"blafoo\"}'"
        sys.exit(3)
    except SyntaxError:
        print "Please use double quotes for labels. e.g.    -l '{\"instance\": \"localhost:9090\", \"example-label\": \"blafoo\"}'"
        sys.exit(3)

    return baseurl, alertname, labels, timeout, statusinfo, ignore_cert, basic_auth, netrc_path

def main(argv):
    args = get_args(argv)
    prom_request = PromRequest(args[0], args[1], args[2], args[3], args[4], args[5], args[6], args[7])
    STATUS = 0
    try:
        STATUS = prom_request.check_alert_status()
    except PromRequestError as e:
        print e
        STATUS = 3
    return STATUS

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))