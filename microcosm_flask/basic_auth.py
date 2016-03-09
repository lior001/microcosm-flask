"""
Basic Auth support.

"""
from base64 import b64encode

from flask.ext.basicauth import BasicAuth
from werkzeug.exceptions import Unauthorized

from microcosm.api import defaults
from microcosm_flask.errors import with_headers


def encode_basic_auth(username, password):
    """
    Encode basic auth credentials.

    """
    return "Basic {}".format(
        b64encode("{}:{}".format(
            username,
            password,
        ))
    )


class ConfigBasicAuth(BasicAuth):
    """
    Basic auth decorator that pulls credentials from static configuration.

    This decorator is sufficient for internal service access control, but should
    not be used for anything truly sensitive.

    """

    def __init__(self, app, credentials):
        super(ConfigBasicAuth, self).__init__(app)
        self.credentials = credentials

    def check_credentials(self, username, password):
        """
        Override credential checking to use configured credentials.

        """
        return password is not None and self.credentials.get(username, None) == password

    def challenge(self):
        """
        Override challenge to raise an exception that will trigger regular error handling.

        """
        response = super(ConfigBasicAuth, self).challenge()
        raise with_headers(Unauthorized(), response.headers)


@defaults(
    credentials={
        "default": "secret",
    }
)
def configure_basic_auth(graph):
    """
    Configure a basic auth decorator.

    """
    # use the metadata name if no realm is defined
    graph.config.setdefault("BASIC_AUTH_REALM", graph.metadata.name)
    return ConfigBasicAuth(
        app=graph.flask,
        # wrap in dict to allow lists of items as well as dictionaries
        credentials=dict(graph.config.basic_auth.credentials),
    )
