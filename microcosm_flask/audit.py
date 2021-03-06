"""
Audit log support for Flask routes.

"""
from collections import namedtuple
from functools import wraps
from logging import getLogger
from json import loads
from traceback import format_exc

from flask import current_app, g, request
from microcosm.api import defaults
from microcosm_flask.errors import (
    extract_context,
    extract_error_message,
    extract_include_stack_trace,
    extract_status_code,
)
from microcosm_logging.timing import elapsed_time


AuditOptions = namedtuple("AuditOptions", [
    "include_request_body",
    "include_response_body",
])


SKIP_LOGGING = "_microcosm_flask_skip_audit_logging"


def skip_logging(func):
    """
    Decorate a function so logging will be skipped.

    """
    setattr(func, SKIP_LOGGING, True)
    return func


def should_skip_logging(func):
    """
    Should we skip logging for this handler?

    """
    return getattr(func, SKIP_LOGGING, False)


def audit(func):
    """
    Record a Flask route function in the audit log.

    Generates a JSON record in the Flask log for every request.

    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        options = AuditOptions(
            include_request_body=True,
            include_response_body=True,
        )
        return _audit_request(options, func, None, *args, **kwargs)

    return wrapper


class RequestInfo(object):
    """
    Capture of key information for requests.

    """
    def __init__(self, options, func, request_context):
        self.options = options
        self.operation = request.endpoint
        self.func = func.__name__
        self.method = request.method
        self.request_context = request_context
        self.timing = dict()

        self.error = None
        self.stack_trace = None
        self.request_body = None
        self.response_body = None
        self.status_code = None
        self.success = None

    def to_dict(self):
        dct = dict(
            operation=self.operation,
            func=self.func,
            method=self.method,
            **self.timing
        )

        if self.request_context is not None:
            dct.update(self.request_context())

        if self.success is True:
            dct.update(
                success=self.success,
                status_code=self.status_code,
            )
        if self.success is False:
            dct.update(
                success=self.success,
                message=extract_error_message(self.error)[:2048],
                context=extract_context(self.error),
                stack_trace=self.stack_trace,
                status_code=self.status_code,
            )

        self.post_process_request_body(dct)
        self.post_process_response_body(dct)

        return dct

    def log(self, logger):
        if self.status_code == 500:
            # something actually went wrong; investigate
            logger.warning(self.to_dict())
        else:
            # usually log at INFO; a raised exception can be an error or expected behavior (e.g. 404)
            logger.info(self.to_dict())

    def capture_request(self):
        if not current_app.debug:
            # only capture request body on debug
            return

        if not self.options.include_request_body:
            # only capture request body if requested
            return

        if not request.get_json(force=True, silent=True):
            # only capture request body if json
            return

        self.request_body = request.get_json(force=True)

    def capture_response(self, response):
        self.success = True

        body, self.status_code = parse_response(response)

        if not current_app.debug:
            # only capture responsebody on debug
            return

        if not self.options.include_response_body:
            # only capture response body if requested
            return

        if not body:
            # only capture request body if there is one
            return

        try:
            self.response_body = loads(body)
        except (TypeError, ValueError):
            # not json
            pass

    def capture_error(self, error):
        self.error = error
        self.status_code = extract_status_code(error)
        self.success = 0 < self.status_code < 400
        include_stack_trace = extract_include_stack_trace(error)
        self.stack_trace = format_exc(limit=10) if (not self.success and include_stack_trace) else None

    def post_process_request_body(self, dct):
        if g.get("hide_body") or not self.request_body:
            return

        for name, new_name in g.get("show_request_fields", {}).items():
            try:
                value = self.request_body.pop(name)
                self.request_body[new_name] = value
            except KeyError:
                pass

        for field in g.get("hide_request_fields", []):
            try:
                del self.request_body[field]
            except KeyError:
                pass

        dct.update(
            request_body=self.request_body,
        )

    def post_process_response_body(self, dct):
        if g.get("hide_body") or not self.response_body:
            return

        for name, new_name in g.get("show_response_fields", {}).items():
            try:
                value = self.response_body.pop(name)
                self.response_body[new_name] = value
            except KeyError:
                pass

        for field in g.get("hide_response_fields", []):
            try:
                del self.response_body[field]
            except KeyError:
                pass

        dct.update(
            response_body=self.response_body,
        )


def _audit_request(options, func, request_context, *args, **kwargs):  # noqa: C901
    """
    Run a request function under audit.

    """
    logger = getLogger("audit")

    request_info = RequestInfo(options, func, request_context)
    response = None

    request_info.capture_request()
    try:
        # process the request
        with elapsed_time(request_info.timing):
            response = func(*args, **kwargs)
    except Exception as error:
        request_info.capture_error(error)
        raise
    else:
        request_info.capture_response(response)
        return response
    finally:
        if not should_skip_logging(func):
            request_info.log(logger)


def parse_response(response):
    """
    Parse a Flask response into a body and status code.

    The returned value from a Flask view could be:
        * a tuple of (response, status) or (response, status, headers)
        * a Response object
        * a string
    """
    if isinstance(response, tuple) and len(response) > 1:
        return response[0], response[1]
    try:
        return response.data, response.status_code
    except AttributeError:
        return response, 200


@defaults(
    include_request_body=True,
    include_response_body=True,
)
def configure_audit_decorator(graph):
    """
    Configure the audit decorator.

    Example Usage:

        @graph.audit
        def login(username, password):
            ...
    """
    include_request_body = graph.config.audit.include_request_body
    include_response_body = graph.config.audit.include_response_body

    def _audit(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            options = AuditOptions(
                include_request_body=include_request_body,
                include_response_body=include_response_body,
            )
            return _audit_request(options, func, graph.request_context,  *args, **kwargs)
        return wrapper
    return _audit
