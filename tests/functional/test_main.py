# -*- coding: utf-8 -*-
"""Test Main Module

This module contains the tests for the OpenRecords `/` endpoint.

.. _Flask Tutorial:
   http://flask.pocoo.org/docs/1.0/tutorial/
"""

import pytest

from flask import Flask
from app.models import Emails


def test_index(client: Flask.test_client):
    """ Test the `/` endpoint works properly.

    Args:
        client (Flask.test_client): The test client used to access the endpoint
    """
    response = client.get("/")
    assert b"""<button class="btn btn-primary btn-lg btn-block request-record-button-size">Check for Similar Requests</button>""" in response.data
    assert b"""<button class="btn btn-primary btn-lg btn-block request-record-button-size">Request a Record</button>""" in response.data


def test_status(client: Flask.test_client):
    """Test the `/index.html` and `/status` status endpoint always returns 200 on GET

    Args:
        client (Flask.test_client): The test client used to access the endpoint
    """
    # Test `/index.html`
    response = client.get("/index.html")
    assert response.status_code == 200

    response = client.post("/index.html")
    assert response.status_code == 405

    # Test `/status`
    response = client.get("/status")
    assert response.status_code == 200
    response = client.post("/status")
    assert response.status_code == 405


def test_get_contact(
        client: Flask.test_client
):
    """Test the technical support endpoint / form for OpenRecords

    Args:
        client (Flask.test_client): Test client used to access the technical-support page
    """

    # Test `/technical-support`
    response = client.get("/contact")
    assert response.status_code == 200
    assert b'<h2 class="text-center">Technical Support</h2>' in response.data
    assert b"Use this form only for technical support." in response.data


@pytest.mark.parametrize(
    ("name", "email", "subject", "message", "app_response"),
    (
            (
                    "John Doris",
                    "john.doris@records.nyc.gov",
                    "Test Subject",
                    "Test Message",
                    b"Your message has been sent. We will get back to you.",
            ),
            ("", "john.doris@records.nyc.gov", "Test Subject",
             "Test Message", b"Cannot send email."),
            ("John Doris", "", "Test Subject", "Test Message", b"Cannot send email."),
            ("John Doris", "john.doris@records.nyc.gov",
             "", "Test Message", b"Cannot send email."),
            ("John Doris", "john.doris@records.nyc.gov",
             "Test Subject", "", b"Cannot send email"),
            ("", "", "", "", b"Cannot send email."),
    ),
)
def test_post_contact(
        client: Flask.test_client, name: str, email: str, subject: str, message: bytes, app_response: str
):
    """Test the technical support form for OpenRecords

    Args:
        client (Flask.test_client): Test client used to access the technical-support page
        name (str): Name of the person submitting the form (required)
        email (str): Email of the person submitting the form (required)
        subject (str): Subject of the message being sent out
        message (str): Message being sent out
        app_response (str): Message displayed after post
    """
    data = {"name": name, "email": email, "subject": subject,
            "message": message, "app_response": app_response}
    response = client.post("/contact", data=data)
    assert response.status_code == 200
    assert app_response in response.data

def test_get_technical_support(
        client: Flask.test_client
):
    """Test the technical support endpoint / form for OpenRecords

    Args:
        client (Flask.test_client): Test client used to access the technical-support page
    """

    # Test `/technical-support`
    response = client.get("/technical-support")
    assert response.status_code == 200
    assert b'<h2 class="text-center">Technical Support</h2>' in response.data
    assert b"Use this form only for technical support." in response.data


@pytest.mark.parametrize(
    ("name", "email", "subject", "message", "app_response"),
    (
            (
                    "John Doris",
                    "john.doris@records.nyc.gov",
                    "Test Subject",
                    "Test Message",
                    b"Your message has been sent. We will get back to you.",
            ),
            ("", "john.doris@records.nyc.gov", "Test Subject",
             "Test Message", b"Cannot send email."),
            ("John Doris", "", "Test Subject", "Test Message", b"Cannot send email."),
            ("John Doris", "john.doris@records.nyc.gov",
             "", "Test Message", b"Cannot send email."),
            ("John Doris", "john.doris@records.nyc.gov",
             "Test Subject", "", b"Cannot send email"),
            ("", "", "", "", b"Cannot send email."),
    ),
)
def test_post_technical_support(
        client: Flask.test_client, name: str, email: str, subject: str, message: bytes, app_response: str
):
    """Test the technical support form for OpenRecords

    Args:
        client (Flask.test_client): Test client used to access the technical-support page
        name (str): Name of the person submitting the form (required)
        email (str): Email of the person submitting the form (required)
        subject (str): Subject of the message being sent out
        message (str): Message being sent out
        app_response (str): Message displayed after post
    """
    data = {"name": name, "email": email, "subject": subject,
            "message": message, "app_response": app_response}
    response = client.post("/technical-support", data=data)
    assert response.status_code == 200
    assert app_response in response.data