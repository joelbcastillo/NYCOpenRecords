# -*- coding: utf-8 -*-
"""Test Factory Module

This module contains the tests for the OpenRecords Application Factory
"""
import os

import flask
import json
import pytest


from app import create_app


def test_default_config():
    """Test the default config class is the DevelopmentConfig"""
    assert isinstance(create_app(), flask.app.Flask)


def test_testing_config():
    """Test the app.testing variable is set when using the testing config."""
    assert create_app(config_name='testing', jobs_enabled=False).testing