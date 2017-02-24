"""
Alias convention tests.

"""
from uuid import uuid4

from hamcrest import (
    all_of,
    assert_that,
    contains,
    equal_to,
    has_entry,
    has_item,
    has_key,
    is_,
    is_not,
)
from json import loads
from marshmallow import fields, Schema
from microcosm.api import create_object_graph
from six import b, BytesIO

from microcosm_flask.namespaces import Namespace
from microcosm_flask.conventions.base import EndpointDefinition
from microcosm_flask.conventions.swagger import configure_swagger
from microcosm_flask.conventions.upload import configure_upload
from microcosm_flask.operations import Operation
from microcosm_flask.swagger.definitions import build_path
from microcosm_flask.tests.conventions.fixtures import Person


def upload_file(files, extra):
    pass


def upload_file_for(files, person_id):
    return dict(
        id=person_id,
    )


class FileExtraSchema(Schema):
    extra = fields.String(missing="something")


class FileResponseSchema(Schema):
    id = fields.UUID(required=True)


UPLOAD_MAPPINGS = {
    Operation.Upload: EndpointDefinition(
        func=upload_file,
        request_schema=FileExtraSchema(),
    ),
}

UPLOAD_FOR_MAPPINGS = {
    Operation.UploadFor: EndpointDefinition(
        func=upload_file_for,
        response_schema=FileResponseSchema(),
    ),
}


class TestUpload(object):

    def setup(self):
        self.graph = create_object_graph(name="example", testing=True)

        self.ns = Namespace(subject="file")
        self.relation_ns = Namespace(subject=Person, object_="file")
        configure_upload(self.graph, self.ns, UPLOAD_MAPPINGS)
        configure_upload(self.graph, self.relation_ns, UPLOAD_FOR_MAPPINGS)
        configure_swagger(self.graph)

        self.client = self.graph.flask.test_client()

    def test_upload_url_for(self):
        with self.graph.app.test_request_context():
            url = self.ns.url_for(Operation.Upload)
        assert_that(url, is_(equal_to("http://localhost/api/file")))

    def test_upload_for_url_for(self):
        with self.graph.app.test_request_context():
            url = self.relation_ns.url_for(Operation.UploadFor, person_id=1)
        assert_that(url, is_(equal_to("http://localhost/api/person/1/file")))

    def test_upload_swagger_path(self):
        with self.graph.app.test_request_context():
            path = build_path(Operation.Upload, self.ns)
        assert_that(path, is_(equal_to("/api/file")))

    def test_upload_for_swagger_path(self):
        with self.graph.app.test_request_context():
            path = build_path(Operation.UploadFor, self.relation_ns)
        assert_that(path, is_(equal_to("/api/person/{person_id}/file")))

    def test_swagger(self):
        response = self.client.get("/api/swagger")
        assert_that(response.status_code, is_(equal_to(200)))
        data = loads(response.data)

        upload = data["paths"]["/file"]["post"]
        upload_for = data["paths"]["/person/{person_id}/file"]["post"]

        # both endpoints return form data
        assert_that(
            upload["consumes"],
            contains("multipart/form-data"),
        )
        assert_that(
            upload_for["consumes"],
            contains("multipart/form-data"),
        )

        # one endpoint gets an extra query string parameter (and the other doesn't)
        assert_that(
            upload["parameters"],
            has_item(
                has_entry("name", "extra"),
            ),
        )
        assert_that(
            upload_for["parameters"],
            has_item(
                is_not(has_entry("name", "extra")),
            ),
        )

        # one endpoint gets a custom response type (and the other doesn't)
        assert_that(
            upload["responses"],
            all_of(
                has_key("204"),
                is_not(has_key("200")),
                has_entry("204", is_not(has_key("schema"))),
            ),
        )
        assert_that(
            upload_for["responses"],
            all_of(
                has_key("200"),
                is_not(has_key("204")),
                has_entry("200", has_entry("schema", has_entry("$ref", "#/definitions/FileResponse"))),
            ),
        )

    def test_upload(self):
        response = self.client.post(
            "/api/file",
            data=dict(
                file=(BytesIO(b("Hello World\n")), "hello.txt"),
            ),
        )
        assert_that(response.status_code, is_(equal_to(204)))

    def test_upload_for(self):
        person_id = uuid4()
        response = self.client.post(
            "/api/person/{}/file".format(person_id),
            data=dict(
                file=(BytesIO(b("Hello World\n")), "hello.txt"),
            ),
        )
        assert_that(response.status_code, is_(equal_to(200)))
        response_data = loads(response.get_data().decode("utf-8"))
        assert_that(response_data, is_(equal_to(dict(
            id=str(person_id),
        ))))
