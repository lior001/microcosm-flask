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


def _audit_request(options, func, request_context, *args, **kwargs):  # noqa: C901
    """
    Run a request function under audit.

    """
    logger = getLogger("audit")

    response = None

    # always include these fields
    audit_dict = dict(
        operation=request.endpoint,
        func=func.__name__,
        method=request.method,
    )

    # include request body on debug (if any)
    if all((
        current_app.debug,
        options.include_request_body,
        request.get_json(force=True, silent=True),
    )):
        request_body = request.get_json(force=True)
    else:
        request_body = None

    response_body = None

    # include headers (conditionally)
    if request_context is not None:
        audit_dict.update(request_context())

    # process the request
    try:
        with elapsed_time(audit_dict):
            response = func(*args, **kwargs)
    except Exception as error:
        status_code = extract_status_code(error)
        success = 0 < status_code < 400
        audit_dict.update(
            success=success,
            message=extract_error_message(error)[:2048],
            context=extract_context(error),
            stack_trace=None if success else format_exc(limit=10),
            status_code=status_code,
        )
        raise
    else:
        body, status_code = parse_response(response)

        audit_dict.update(
            success=True,
            status_code=status_code,
        )

        # include response body on debug (if any)
        if all((
                current_app.debug,
                options.include_response_body,
                body,
        )):
            try:
                response_body = loads(body)
            except (TypeError, ValueError):
                # not json
                audit_dict["response_body"] = body

        return response
    finally:
        # determine whether to show/hide body based on the g values set during func
        if not g.get("hide_body"):
            if request_body:
                for name, new_name in g.get("show_request_fields", {}).items():
                    try:
                        value = request_body.pop(name)
                        request_body[new_name] = value
                    except KeyError:
                        pass
                    pass
                for field in g.get("hide_request_fields", []):
                    try:
                        del request_body[field]
                    except KeyError:
                        pass
                audit_dict["request_body"] = request_body

            if response_body:
                for name, new_name in g.get("show_response_fields", {}).items():
                    try:
                        value = response_body.pop(name)
                        response_body[new_name] = value
                    except KeyError:
                        pass
                    pass
                for field in g.get("hide_response_fields", []):
                    try:
                        del response_body[field]
                    except KeyError:
                        pass
                audit_dict["response_body"] = response_body

        # always log at INFO; a raised exception can be an error or expected behavior (e.g. 404)
        if not should_skip_logging(func):
            logger.info(audit_dict)


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
