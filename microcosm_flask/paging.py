"""
Pagination support.

"""
from flask import request
from marshmallow import fields, Schema

from microcosm_flask.linking import Link, Links
from microcosm_flask.operations import Operation


def identity(x):
    """
    Identity function.

    """
    return x


class PageSchema(Schema):
    offset = fields.Integer(missing=None)
    limit = fields.Integer(missing=None)


def make_paginated_list_schema(ns, item_schema):
    """
    Generate a paginated list schema.

    :param ns: a `Namespace` for the list's item type
    :param item_schema: a `Schema` for the list's item type

    """

    class PaginatedListSchema(Schema):
        __alias__ = "{}_list".format(ns.subject_name)

        offset = fields.Integer(required=True)
        limit = fields.Integer(required=True)
        count = fields.Integer(required=True)
        items = fields.List(fields.Nested(item_schema), required=True)
        _links = fields.Raw()

    return PaginatedListSchema


class Page(object):

    def __init__(self, offset=None, limit=None, **rest):
        self.offset = self.default_offset if offset is None else offset
        self.limit = self.default_limit if limit is None else limit
        self.rest = rest

    @property
    def default_offset(self):
        return 0

    @property
    def default_limit(self):
        try:
            return int(request.headers["X-Request-Limit"])
        except:
            return 20

    @classmethod
    def from_query_string(cls, qs):
        """
        Create a page from a query string dictionary.

        This dictionary should probably come from `PageSchema.from_request()`.

        """
        dct = qs.copy()
        offset = dct.pop("offset", None)
        limit = dct.pop("limit", None)
        return cls(
            offset=offset,
            limit=limit,
            **dct
        )

    def next(self):
        return Page(
            offset=self.offset + self.limit,
            limit=self.limit,
            **self.rest
        )

    def prev(self):
        return Page(
            offset=self.offset - self.limit,
            limit=self.limit,
            **self.rest
        )

    def to_dict(self, as_str=False):
        return dict(self.to_tuples(as_str=as_str))

    def to_tuples(self, as_str=True):
        """
        Convert to tuples for deterministic order when passed to urlencode.

        """
        value_func = str if as_str else identity

        return [
            ("offset", self.offset),
            ("limit", self.limit),
        ] + [
            (key, value_func(self.rest[key]))
            for key in sorted(self.rest.keys())
        ]


class PaginatedList(object):

    def __init__(self,
                 ns,
                 page,
                 items,
                 count,
                 schema=None,
                 operation=Operation.Search,
                 **extra):
        self.ns = ns
        self.page = page
        self.items = items
        self.count = count
        self.schema = schema
        self.operation = operation
        self.extra = extra

    def to_dict(self):
        return dict(
            count=self.count,
            items=[
                self.schema.dump(item).data if self.schema else item
                for item in self.items
            ],
            _links=self._links,
            **self.page.to_dict(as_str=True)
        )

    @property
    def offset(self):
        return self.page.offset

    @property
    def limit(self):
        return self.page.limit

    @property
    def _links(self):
        return self.links.to_dict()

    @property
    def links(self):
        links = Links()
        links["self"] = Link.for_(self.operation, self.ns, qs=self.page.to_tuples(), **self.extra)
        if self.page.offset + self.page.limit < self.count:
            links["next"] = Link.for_(self.operation, self.ns, qs=self.page.next().to_tuples(), **self.extra)
        if self.page.offset > 0:
            links["prev"] = Link.for_(self.operation, self.ns, qs=self.page.prev().to_tuples(), **self.extra)
        return links
