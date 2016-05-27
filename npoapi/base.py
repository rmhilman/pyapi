import abc
import argparse
import logging
import sys
import os
import copy
import npoapi
import urllib.request
import codecs


class NpoApiBase:
    __metaclass__ = abc.ABCMeta
    EPILOG = """
    DEBUG=true and ENV=<dev|test|prod> environment variables are recognized.
    Credentials are read from a config file. If such a file does not exist it will offer to create one.
    """

    def __init__(self, env: str = None, debug: bool = False, accept: str = None):
        """

        """
        logging.basicConfig(format='%(levelname)s %(message)s')
        self.force_create_config = False
        self.logger = logging.getLogger("Npo")
        self._env = env
        self.env(env)
        self.debug(debug)
        self.accept(accept)
        self.code = None

    @abc.abstractmethod
    def env(self, e):
        """"Sets environment"""
        self._env = e
        self.actualenv = self._env if self._env else "test"
        return self

    def debug(self, arg=True):
        self.logger.setLevel(level=logging.DEBUG if arg else logging.INFO)
        return self

    def accept(self, arg=None):
        if arg:
            self._accept = arg
        else:
            self._accept = "application/json"
        return self

    def read_environmental_variables(self):

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
        Logs in using configuration file. Considered using json (no comments-> unusable) or configparser (nearly properties, but headings are required..)
        So, now it simply parses the file itself.
        :param create_config_file: If there is no existing config file, offer to create one
        :param read_environment: If this is set to true, shel environment variables like DEBUG and ENV will be recognized
        """
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
                self.logger.debug("not a file " + file)

        settings = {}
        if config_file:
            self.logger.debug("Reading " + config_file + " for env " + self.actualenv)
            properties = self.read_properties_file(config_file)
            self.read_settings_from_properties(properties, settings)

        if not config_file and create_config_file:
            print("No configuration file found. Now creating.")
            self.force_create_config = True

        if self.force_create_config:
            self.create_config(settings)
            config_file = None
            for file in config_files:
                config_file = os.path.normpath(file)
                if os.access(os.path.dirname(config_file), os.W_OK):
                    self.logger.debug("Found " + config_file)
                    break
                else:
                    self.logger.debug("Not writeable " + config_file)
                    config_file = None

            if config_file:
                with open(config_file, "w") as f:
                    f.write("# Automaticly generated by " + __file__ + "\n")
                    for key in settings:
                        if len(key.split(".")) == 1:
                            f.write(key + "=" + settings[key] + "\n")
                            f.write(key + "." + self.actualenv + "=" + settings[key] + "\n")
                        if len(key.split(".")) == 2:
                            f.write(key + "=" + settings[key] + "\n")
            else:
                print("(Configuration could not be saved since no file of %s is writable" % str(config_files))

        if self.logger.isEnabledFor(logging.DEBUG):
            settings_for_log = copy.copy(settings)
            self.anonymize_for_logging(settings_for_log)
            self.logger.debug("settings" + str(settings_for_log))

        self.logger.debug("Reading settings")
        self.read_settings(settings)

        return self

    def read_properties_file(self, config_file, properties=None):
        if properties is None:
            properties = {}
        with open(config_file, "r") as f:
            for line in f:
                l = line.strip()
                if l and not l.startswith("#"):
                    key, value = l.split("=", 2)
                    properties[key] = value.strip('" \t')
        return properties

    def read_settings_from_properties(self, properties, settings=None):
        if settings is None:
            settings = {}
        for key, value in properties.items():
            split = key.split('.', 2)
            if len(split) == 1:
                settings[key.strip().lower()] = value.strip('" \t')
        for key, value in properties.items():
            split = key.split('.', 2)
            if len(split) == 2:
                usedkey, e = split[0], split[1]
                if e == self.actualenv:
                    settings[usedkey.strip().lower()] = value.strip('" \t')
                    self.logger.debug("%s %s %s %s", e, usedkey, key, value)
        return settings

    def anonymize_for_logging(self, settings_for_log):
        if 'secret' in settings_for_log:
            settings_for_log['secret'] = "xxx"

        if 'user' in settings_for_log:
            settings_for_log['user'] = settings_for_log['user'].split(":", 1)[0] + ":xxx"
        return

    @abc.abstractmethod
    def create_config(self, settings):
        """

        """

        return self

    @abc.abstractmethod
    def read_settings(self, settings):
        """
        """
        return

    def command_line_client(self, description=None, read_environment=True, create_config_file=True):
        self.common_arguments(description=description)
        return self.configured_login(read_environment=read_environment, create_config_file=create_config_file)

    def add_argument(self, *args, **kwargs):
        self.argument_parser.add_argument(*args, **kwargs)

    def common_arguments(self, description=None):
        parent_args = argparse.ArgumentParser(add_help=False)
        parent_args.add_argument('-v', "--version", action="store_true", help="show current version")
        parent_args.add_argument('-a', "--accept", type=str, default=None, choices={"json", "xml"})
        parent_args.add_argument('-e', "--env", type=str, default=None, choices={"test", "prod", "dev", "localhost"})
        parent_args.add_argument('-c', "--createconfig", action='store_true', help="Create config")
        parent_args.add_argument('-d', "--debug", action='store_true', help="Switch on debug logging")
        pargs = parent_args.parse_args(
            filter(lambda e: e in ["-d", "--debug", "-c", "--createconfig", "-v", "--version"], sys.argv))
        self.debug(pargs.debug)
        if pargs.version:
            print(npoapi.__version__)
            exit(0)
        self.force_create_config = pargs.createconfig
        self.argument_parser = argparse.ArgumentParser(description=description,
                                                       parents=[parent_args],
                                                       epilog=NpoApiBase.EPILOG)

    def parse_args(self):
        args = self.argument_parser.parse_args()
        self.env(args.env)
        self.debug(args.debug)
        self.accept("application/" + args.accept if args.accept else None)
        return args

    def get_response(self, req, url):
        try:
            response = urllib.request.urlopen(req)
            self.code = response.getcode()
            self.logger.debug("response code: " + str(response.getcode()))
            self.logger.debug("response headers: " + str(response.getheaders()))
            return response
        except urllib.error.URLError as ue:
            if type(ue.reason) is str:
                self.logger.error('%s: %s', url, ue.reason)
                self.code = 1
            else:
                self.logger.error('%s: %s %s', ue.reason.errno, url, ue.reason.strerror)
                self.code = ue.reason.errno
            self.logger.error("%s", ue.read().decode("utf-8"))
            return None
        except urllib.error.HTTPError as he:
            self.code = he.code
            self.logger.error("%s: %s\n%s", he.code, he.msg, he.read().decode("utf-8"))
            return None

    def data_to_bytes(self, data, content_type=None):
        if data:
            import pyxb
            if isinstance(data, pyxb.binding.basis.complexTypeDefinition):
                content_type = "application/xml"
                data = data.toxml()
            elif os.path.isfile(data):
                if content_type is None:
                    if data.endswith(".json"):
                        content_type = "application/json"
                    elif data.endswith(".xml"):
                        content_type = "application/xml"

                self.logger.debug("" + data + " is file, reading it in as " + content_type)
                with codecs.open(data, 'r', 'utf-8') as myfile:
                    data = myfile.read()
                    self.logger.debug("Found data " + data)

        return data, content_type

    def to_object(self, data, validate=False):
        if data.validateBinding:
            return data
        from npoapi.xml import poms
        object = poms.CreateFromDocument(data)
        if validate:
            object.validateBinding()
        return object

    def parse_xml_or_none(self, data, validate=False):
        import xml
        try:
            self.to_object(data, validate)
        except xml.sax._exceptions.SAXParseException as e:
            self.logger.debug("Not xml")
            return None

    def exit_code(self):
        if self.code is None or 200 <= self.code < 300:
            return 0
        return self.code // 100

    def exit(self):
        sys.exit(self.exit_code())

    @abc.abstractmethod
    def info(self):
        return "ABSTRACT"
