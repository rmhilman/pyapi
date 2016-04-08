import hmac, hashlib, base64
from email import utils
import urllib.request
import logging
import json
import sys
import os
import argparse

class NpoApi:
    EPILOG = """
    DEBUG=true and ENV=<dev|test|prod> environment variables are recognized.
    Credentials are read from a config file. If such a file does not exist it will offer to create one.
    """

    def __init__(self,
                 key:str=None,
                 secret:str=None,
                 env:str=None,
                 origin:str=None,
                 email:str=None,
                 debug:bool=False,
                 accept:str=None):
        """
        Instantiates a client to the NPO Frontend API
        """
        self.key, self.secret, self.origin, self.errors \
            = key, secret, origin, email
        self.env(env)
        self.debug(debug)
        self.accept(accept)

    def login(self, key, secret):
        self.key = key
        self.secret = secret
        return self

    def env(self, e):
        self._env = e
        if e == "prod":
            self.url = "https://rs.poms.omroep.nl/v1"
        elif e == None or e == "test":
            self.url = "https://rs-test.poms.omroep.nl/v1"
        elif e == "dev":
            self.url = "https://rs-dev.poms.omroep.nl/v1"
        elif e == "localhost":
            self.url = "http://localhost:8070/v1"
        else:
            self.url = e
        return self

    def debug(self, arg=True):
        if arg:
            import logging
            logging.basicConfig(level=logging.DEBUG, format='%(levelname)s %(message)s')
        return self

    def accept(self, arg=None):
        if arg:
            self._accept = arg
        else:
            self._accept = "application/json"
        return self

    def read_environmental_variables(self):
        import os

        if self._env == None:
            if 'ENV' in os.environ:
                self.env(os.environ['ENV'])
            else:
                self.env('test')

        if 'DEBUG' in os.environ and os.environ['DEBUG'] == 'true':
            self.debug()

        return self

    def configured_login(self, read_environment=False, create_config_file=False):
        """
        Logs in using configuration file. Considered using json (no comments-> unusable) or configparser (nearly properties, but heading are required..)
        So, now it simply parses the file itself.
        :param create_config_file: If there is no existing config file, offer to create one
        :param read_environment: If this is set to true, shel environment variables like DEBUG and ENV will be recognized
        """
        import os
        if read_environment:
            self.read_environmental_variables()

        config_files = [
            os.path.join(os.path.expanduser("~"), "conf", "creds.properties"),
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "creds.properties"),
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "creds.sh"),
            os.path.join(os.path.dirname(__file__), "creds.properties")]

        config_file = None
        for file in config_files:
            if os.path.isfile(file):
                config_file = os.path.normpath(file)
                break
            else:
                logging.debug("not a file " + file)

        settings = {}
        if config_file:
            logging.debug("Reading " + config_file)
            with open(config_file, "r") as f:
                for line in f:
                    l = line.strip()
                    if l and not l.startswith("#"):
                        key_value = l.split("=", 2)
                        settings[key_value[0].strip().lower()] = key_value[1].strip('" \t')
        elif create_config_file:
            print("No configuration file found. Now creating.")
            settings["apikey"] = input("Your NPO api key?: ")
            settings["secret"] = input("Your NPO api secret?: ")
            settings["origin"] = input("Your NPO api origin?: ")
            for file in config_files:
                config_file = os.path.normpath(file)
                if os.access(os.path.dirname(config_file), os.W_OK):
                    logging.debug("Found " + config_file)
                    break
                else:
                    logging.debug("Not writeable " + config_file)
                    config_file = None

            if config_file:
                with open(config_file, "w") as f:
                    f.write("# Automaticly generated by " + __file__ + "\n")
                    for key in settings:
                        f.write(key + "=" + settings[key] + "\n")
            else:
                print("(Configuration could not be saved since no file of %s is writable" % str(config_files))

        logging.debug(str(settings))
        self.login(settings["apikey"], settings["secret"])
        if "origin" in settings:
            self.origin = settings["origin"]
        return self

    def command_line_client(self, description=None):
        self.common_arguments(description=description)
        return self.configured_login(read_environment=True, create_config_file=True)

    def add_argument(self, *args, **kwargs):
        self.argument_parser.add_argument(*args, **kwargs)

    def common_arguments(self, description=None):

        parent_args = argparse.ArgumentParser(add_help=False)
        parent_args.add_argument('-a', "--accept", type=str, default=None, choices={"json", "xml"})
        parent_args.add_argument('-e', "--env", type=str, default=None, choices={"test", "prod", "dev"})
        parent_args.add_argument('-d', "--debug", action='store_true', help="Switch on debug logging")
        pargs = parent_args.parse_args(filter(lambda e: e in ["-d", "--debug"], sys.argv))
        self.debug(pargs.debug)
        self.argument_parser = argparse.ArgumentParser(description=description, parents=[parent_args],
                                                       epilog=NpoApi.EPILOG)

    def parse_args(self):
        args = self.argument_parser.parse_args()
        if args.env:
            self.env(args.env)
        self.debug(args.debug)
        self.accept("application/" + args.accept if args.accept else None)
        return args

    def info(self):
        return self.key + "@" + self.url

    def authenticate(self, uri=None, now=utils.formatdate()):
        message = "origin:" + self.origin + ",x-npo-date:" + now + ",uri:/v1" + uri
        logging.debug("message: " + message)
        encoded = base64.b64encode(
            hmac.new(self.secret.encode('utf-8'), msg=message.encode('utf-8'), digestmod=hashlib.sha256).digest())
        return "NPO " + self.key + ":" + encoded.decode('utf-8'), now

    def _get_url(self, path, params=None):
        if not params:
            params = {}

        path_for_authentication = path
        if params.items():
            sep = "?"
            for k, v in sorted(params.items()):
                if v is not None:
                    path += sep + k + "=" + urllib.request.quote(str(v))
                    path_for_authentication += "," + k + ":" + str(v)
                    sep = "&"

        url = self.url + path
        return url, path_for_authentication

    def _authentication_headers(self, req, path_for_authentication):
        authorization, date = self.authenticate(path_for_authentication)
        req.add_header("Authorization", authorization)
        req.add_header("X-NPO-Date", date)
        req.add_header("Origin", self.origin)

        logging.debug("url: " + str(req.get_full_url()))

    @staticmethod
    def _get_data(data=None):
        if type(data) == str:
            try:
                json_object = json.JSONDecoder().decode(data)
                return json.JSONEncoder().encode(json_object).encode("UTF-8"), "application/json"
            except json.JSONDecodeError:
                return data.encode("UTF-8"), "application/xml"



        return None,None

    def request(self, path, params=None, accept=None, data=None):
        s = self.stream(path, params, accept, data)
        if s:
            return s.read().decode('utf-8')
        else:
            return ""

    def stream(self, path, params=None, accept=None, data=None):
        if data:
            if os.path.isfile(data):
                logging.debug("" + data + " is file, reading it in")
                with open(data, 'r') as myfile:
                    data = myfile.read()
                    logging.debug("Found data " + data)

        url, path_for_authentication = self._get_url(path, params)
        d, ct = self._get_data(data)
        req = urllib.request.Request(url, data=d)

        if ct:
            req.add_header("Content-Type", ct)

        self._authentication_headers(req, path_for_authentication)
        req.add_header("Accept", accept if accept else self._accept)
        logging.debug("headers: " + str(req.headers))
        try:
            return urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            print(e.code, e.msg, file=sys.stderr)
            return None



