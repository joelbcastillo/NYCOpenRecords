from flask import render_template
from sqlalchemy.orm.exc import NoResultFound
from unittest.mock import patch

from tests.lib.base import BaseTestCase
from tests.lib.tools import (
    UserFactory,
    RequestFactory,
    flask_login_user
)

from app.constants import (
    response_privacy,
    event_type,
    determination_type
)
from app.lib.utils import UserRequestException
from app.models import Determinations, Events
from app.response.utils import (
    add_denial,
    add_closing,
    format_determination_reasons
)


class ResponseUtilsTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.agency_ein_860 = "0860"
        uf = UserFactory()
        self.admin_860 = uf.create_agency_admin(agency_ein=self.agency_ein_860)
        self.rf = RequestFactory()
        self.rf_agency_860 = RequestFactory(agency_ein=self.agency_ein_860)
        self.request = self.rf_agency_860.create_request_as_public_user()
        self.email_content = 'test email body'

    @patch('app.response.utils._send_response_email')
    def test_add_denial(self, send_response_email_patch):
        with flask_login_user(self.admin_860):
            reasons = ['1', '2', '3']
            add_denial(self.request.id, reasons, self.email_content)
            send_response_email_patch.assert_called_once_with(
                self.request.id,
                response_privacy.RELEASE_AND_PUBLIC,
                ''.join((self.email_content, render_template('email_templates/determination_request_text.html',
                                                             title=self.request.title,
                                                             description=self.request.description))),
                'Request {} Closed'.format(self.request.id)
            )
        response = self.request.responses.join(Determinations).filter(
            Determinations.dtype == determination_type.DENIAL).one()
        self.assertEqual(
            [
                response.request_id,
                response.privacy,
                response.dtype,
                response.reason
            ],
            [
                self.request.id,
                response_privacy.RELEASE_AND_PUBLIC,
                determination_type.DENIAL,
                format_determination_reasons(reasons)
            ]
        )
        self.__assert_response_event(event_type.REQ_CLOSED, response, self.admin_860)

    def test_add_denial_invalid_request(self):
        with flask_login_user(self.admin_860):
            reasons = ['1', '2', '3']
            with self.assertRaises(NoResultFound):
                add_denial('FOIL-2017-002-00001', reasons, self.email_content)

    def test_add_denial_already_closed(self):
        with flask_login_user(self.admin_860):
            self.request.close()
            # TODO: create exception on else in add_denial method and raise exception on context
            add_denial(self.request.id, ['1', '2', '3'], self.email_content)

    @patch('app.response.utils._send_response_email')
    def test_add_closing(self, send_response_email_patch):
        with flask_login_user(self.admin_860):
            self.request.acknowledge(days=30)
            self.request.set_agency_description(agency_description='blah')
            self.request.set_agency_description_privacy(privacy=False)
            reasons = ['1', '2', '3']
            add_closing(self.request.id, reasons, self.email_content)
            send_response_email_patch.assert_called_once_with(
                self.request.id,
                response_privacy.RELEASE_AND_PUBLIC,
                self.email_content,
                'Request {} Closed'.format(self.request.id)
            )
        response = self.request.responses.join(Determinations).filter(
            Determinations.dtype == determination_type.CLOSING).one()
        self.assertEqual(
            [
                response.request_id,
                response.privacy,
                response.dtype,
                response.reason
            ],
            [
                self.request.id,
                response_privacy.RELEASE_AND_PUBLIC,
                determination_type.CLOSING,
                format_determination_reasons(reasons)
            ]
        )
        self.__assert_response_event(event_type.REQ_CLOSED, response, self.admin_860)

    def test_add_closing_no_agency_description(self):
        with flask_login_user(self.admin_860):
            self.request.acknowledge(days=30)
            reasons = ['1', '2', '3']
            with self.assertRaises(UserRequestException):
                add_closing(self.request.id, reasons, self.email_content)

    def test_add_closing_file_private(self):
        with flask_login_user(self.admin_860):
            self.request.acknowledge(days=30)
            self.request.add_file()
            reasons = ['1', '2', '3']
            with self.assertRaises(UserRequestException):
                add_closing(self.request.id, reasons, self.email_content)

    def test_add_closing_file_release_public(self):
        request_title_public = self.rf_agency_860.create_request_as_public_user(title_privacy=False)
        with flask_login_user(self.admin_860):
            request_title_public.acknowledge(days=30)
            request_title_public.add_file(privacy=response_privacy.RELEASE_AND_PUBLIC)
            reasons = ['1', '2', '3']
            add_closing(request_title_public.id, reasons, self.email_content)
        response = request_title_public.responses.join(Determinations).filter(
            Determinations.dtype == determination_type.CLOSING).one()
        self.assertEqual(
            [
                response.request_id,
                response.privacy,
                response.dtype,
                response.reason
            ],
            [
                request_title_public.id,
                response_privacy.RELEASE_AND_PUBLIC,
                determination_type.CLOSING,
                format_determination_reasons(reasons)
            ]
        )
        self.__assert_response_event(event_type.REQ_CLOSED, response, self.admin_860, request_title_public)

    def __assert_response_event(self, type_, response, user, request=None):
        event = Events.query.filter_by(response_id=response.id).one()
        self.assertEqual(
            [
                event.user_guid,
                event.auth_user_type,
                event.request_id,
                event.type,
                event.previous_value,
                event.new_value
            ],
            [
                user.guid,
                user.auth_user_type,
                request.id if request is not None else self.request.id,
                type_,
                None,
                response.val_for_events,
            ]
        )
