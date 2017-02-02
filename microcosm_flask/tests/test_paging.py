"""
Paging tests.

"""
from enum import Enum, unique
from uuid import uuid4

from hamcrest import (
    assert_that,
    equal_to,
    is_,
)
from microcosm.api import create_object_graph

from microcosm_flask.conventions.encoding import load_query_string_data
from microcosm_flask.namespaces import Namespace
from microcosm_flask.operations import Operation
from microcosm_flask.paging import Page, PageSchema, PaginatedList


def test_page_from_query_string():
    graph = create_object_graph(name="example", testing=True)

    with graph.flask.test_request_context():
        qs = load_query_string_data(PageSchema())
        page = Page.from_query_string(qs)
        assert_that(page.offset, is_(equal_to(0)))
        assert_that(page.limit, is_(equal_to(20)))


def test_page_defaults():
    graph = create_object_graph(name="example", testing=True)

    with graph.flask.test_request_context():
        page = Page()

    assert_that(page.to_dict(), is_(equal_to({
        "offset": 0,
        "limit": 20
    })))


def test_page_to_dict():
    page = Page(0, 10)
    assert_that(page.to_dict(), is_(equal_to({
        "offset": 0,
        "limit": 10
    })))


def test_page_next():
    page = Page(0, 10).next()
    assert_that(page.offset, is_(equal_to(10)))
    assert_that(page.limit, is_(equal_to(10)))


def test_page_prev():
    page = Page(20, 10).prev()
    assert_that(page.offset, is_(equal_to(10)))
    assert_that(page.limit, is_(equal_to(10)))


def test_paginated_list_to_dict():
    graph = create_object_graph(name="example", testing=True)
    ns = Namespace(subject="foo")

    @graph.route(ns.collection_path, Operation.Search, ns)
    def search_foo():
        pass

    paginated_list = PaginatedList(ns, Page(2, 2), ["1", "2"], 10)

    with graph.flask.test_request_context():
        assert_that(paginated_list.to_dict(), is_(equal_to({
            "count": 10,
            "items": [
                "1",
                "2",
            ],
            "offset": 2,
            "limit": 2,
            "_links": {
                "self": {
                    "href": "http://localhost/api/foo?offset=2&limit=2",
                },
                "next": {
                    "href": "http://localhost/api/foo?offset=4&limit=2",
                },
                "prev": {
                    "href": "http://localhost/api/foo?offset=0&limit=2",
                },
            }
        })))


def test_paginated_list_relation_to_dict():
    graph = create_object_graph(name="example", testing=True)
    ns = Namespace(subject="foo", object_="bar")

    @graph.route(ns.relation_path, Operation.SearchFor, ns)
    def search_foo():
        pass

    paginated_list = PaginatedList(
        ns,
        Page(2, 2),
        ["1", "2"],
        10,
        operation=Operation.SearchFor,
        foo_id="FOO_ID",
    )

    with graph.flask.test_request_context():
        assert_that(paginated_list.to_dict(), is_(equal_to({
            "count": 10,
            "items": [
                "1",
                "2",
            ],
            "offset": 2,
            "limit": 2,
            "_links": {
                "self": {
                    "href": "http://localhost/api/foo/FOO_ID/bar?offset=2&limit=2",
                },
                "next": {
                    "href": "http://localhost/api/foo/FOO_ID/bar?offset=4&limit=2",
                },
                "prev": {
                    "href": "http://localhost/api/foo/FOO_ID/bar?offset=0&limit=2",
                },
            }
        })))


@unique
class MyEnum(Enum):
    ONE = u"ONE"
    TWO = u"TWO"

    def __str__(self):
        return self.name


def test_custom_paginated_list():
    graph = create_object_graph(name="example", testing=True)
    ns = Namespace(subject="foo", object_="bar")

    @graph.route(ns.relation_path, Operation.SearchFor, ns)
    def search_foo():
        pass

    uid = uuid4()
    paginated_list = PaginatedList(
        ns,
        Page.from_query_string(dict(offset=2, limit=2, baz="baz", uid=uid, value=MyEnum.ONE)),
        ["1", "2"],
        10,
        operation=Operation.SearchFor,
        foo_id="FOO_ID",
    )

    rest = "baz=baz&uid={}&value=ONE".format(uid)

    with graph.flask.test_request_context():
        assert_that(paginated_list.to_dict(), is_(equal_to({
            "count": 10,
            "items": [
                "1",
                "2",
            ],
            "offset": 2,
            "limit": 2,
            "_links": {
                "self": {
                    "href": "http://localhost/api/foo/FOO_ID/bar?offset=2&limit=2&{}".format(rest),
                },
                "next": {
                    "href": "http://localhost/api/foo/FOO_ID/bar?offset=4&limit=2&{}".format(rest),
                },
                "prev": {
                    "href": "http://localhost/api/foo/FOO_ID/bar?offset=0&limit=2&{}".format(rest),
                },
            },
            "baz": "baz",
            "uid": str(uid),
            "value": "ONE",
        })))
