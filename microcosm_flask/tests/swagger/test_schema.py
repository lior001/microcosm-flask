"""
Test JSON Schema generation.

"""
from hamcrest import (
    assert_that,
    equal_to,
    is_,
)

from enum import Enum, unique
from marshmallow import Schema, fields

from microcosm_flask.fields import EnumField
from microcosm_flask.swagger.schema import build_schema, build_parameter
from microcosm_flask.tests.conventions.fixtures import NewPersonSchema


@unique
class Choices(Enum):
    Profit = "profit"


class NewPersonNameSchema(Schema):
    firstName = fields.Str(attribute="first_name", required=True)


class TestSchema(Schema):
    id = fields.UUID()
    foo = fields.String(description="Foo", default="bar")
    choice = EnumField(Choices)
    names = fields.List(fields.String)
    payload = fields.Dict()
    ref = fields.Nested(NewPersonSchema)
    singleFieldRef = fields.Nested(NewPersonNameSchema, attribute="name", only="first_name")


def test_schema_generation():
    schema = build_schema(NewPersonSchema())
    assert_that(schema, is_(equal_to({
        "type": "object",
        "properties": {
            "firstName": {
                "type": "string",
            },
            "lastName": {
                "type": "string",
            },
        },
        "required": [
            "firstName",
            "lastName",
        ],
    })))


def test_field_description_and_default():
    parameter = build_parameter(TestSchema().fields["foo"])
    assert_that(parameter, is_(equal_to({
        "type": "string",
        "description": "Foo",
        "default": "bar",
    })))


def test_field_format():
    parameter = build_parameter(TestSchema().fields["id"])
    assert_that(parameter, is_(equal_to({
        "type": "string",
        "format": "uuid",
    })))


def test_field_enum():
    parameter = build_parameter(TestSchema().fields["choice"])
    assert_that(parameter, is_(equal_to({
        "type": "string",
        "enum": [
            "Profit",
        ],
    })))


def test_field_array():
    parameter = build_parameter(TestSchema().fields["names"])
    assert_that(parameter, is_(equal_to({
        "type": "array",
        "items": {
            "type": "string",
        }
    })))


def test_field_dict():
    parameter = build_parameter(TestSchema().fields["payload"])
    assert_that(parameter, is_(equal_to({
        "type": "object",
    })))


def test_field_nested():
    parameter = build_parameter(TestSchema().fields["ref"])
    assert_that(parameter, is_(equal_to({
        "$ref": "#/definitions/NewPerson",
    })))


def test_field_nested_with_only():
    # TODO(srt32): how to test...
    parameter = build_parameter(TestSchema().fields["singleFieldRef"])
    assert_that(parameter, is_(equal_to({
        "$ref": "#/definitions/NewPersonName",
    })))
