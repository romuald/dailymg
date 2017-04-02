from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import os
import os.path
import tempfile
import shutil
import unittest
import warnings
import json

try:
    import urllib.request as urllib
except ImportError:
    import urllib2 as urllib

from io import BytesIO

from datetime import datetime

import mock

from dailymg import Dailymg

from freezegun import freeze_time

"""
def side_request(arg):
    print("REQUEST FOR:", arg)
    ret = mock.MagicMock(url=arg)

    return ret


def side_open(arg):
    print("REQUEST READ FOR:", arg)

    ret = mock.MagicMock()
    ret.read.side_effect = [b'{"photos": [], "url": "%s"}' % arg.url]
    return ret
    return '{"photos": []}'


class TestBase(unittest.TestCase):
    def setUp(self):
        self.tty_patch = mock.patch.object(Dailymg, 'isatty')

        self.m_tty = self.tty_patch.start()
        self.m_tty.return_value = False

        self.urlopen_patch = mock.patch('dailymg.dailymg.urllib.urlopen')
        self.urlrequest_patch = mock.patch('dailymg.dailymg.urllib.Request')

        self.m_1 = self.urlopen_patch.start()
        self.m_1.side_effect = side_open
        self.m_2 = self.urlrequest_patch.start()
        self.m_2.side_effect = side_request

        self.directory = tempfile.mkdtemp(suffix='-test-dailymg')
        print(self.directory)

    def tearDown(self):
        self.tty_patch.stop()
        self.urlopen_patch.stop()
        self.urlrequest_patch.stop()
        shutil.rmtree(self.directory)

    def test_base_configure(self):
        mg = Dailymg(self.directory)
        mg.configure()

        assert os.path.isdir(os.path.join(self.directory, '.dailymg'))
        assert os.path.isdir(os.path.join(self.directory, '.dailymg',
                                          'metadata'))

        assert mg.days == Dailymg.days
        assert mg.per_day == Dailymg.per_day
        assert mg.ratio == Dailymg.ratio
        assert mg.ratio_delta == Dailymg.ratio_delta

    #@mock.patch('dailymg.dailymg.urllib.urlopen')
    #@mock.patch('dailymg.dailymg.urllib.Request')
    def test_foo(self, ):#m_request, m_urlopen):
        mg = Dailymg(self.directory)
        mg.configure()
        mg.days = 2
        print("Y?",  mg.get_day_metadata(datetime(2015, 1, 1)))
        #print(mg.get_photos())

"""


class MockHTTPHandler(urllib.HTTPHandler):

    @classmethod
    def load_fixtures(cls):
        path = os.path.join(os.path.dirname(__file__), 'fixtures', 'http.json')
        with open(path) as fixture_file:
            fixtures = json.load(fixture_file)

        cls.data = {}
        for fixture in fixtures:
            url = fixture['url']
            if url in cls.data:
                raise ValueError('%s defined twice in fixtures' % url)

            fixture['data'] = json.dumps(fixture['data']).encode('utf-8')
            cls.data[url] = fixture

    @classmethod
    def install(cls):
        cls.load_fixtures()

        previous = urllib._opener
        urllib.install_opener(urllib.build_opener(cls))
        return previous

    @classmethod
    def remove(cls, previous=None):
        urllib.install_opener(previous)

    def mock_response(self, req):
        url = req.get_full_url()

        print("incomming request:", url)

        resdata = None
        rescode = 200
        rescodes = {200: 'OK', 404: 'Not found'}
        headers = {}

        data = self.data.get(url)
        if data is None:
            raise RuntimeError('Unhandled URL', url)

        response = urllib.addinfourl(BytesIO(data['data']), headers, url)
        response.code = data['code']
        response.msg = rescodes.get(response.code)

        return response

    http_open = mock_response


class TestOther(unittest.TestCase):

    def setUp(self):
        patch = mock.patch.object(Dailymg, 'isatty', return_value=False)
        patch.start()
        self.addCleanup(patch.stop)

        self.directory = tempfile.mkdtemp(suffix='-test-dailymg')
        self.addCleanup(shutil.rmtree, self.directory)

        previous = MockHTTPHandler.install()
        self.addCleanup(MockHTTPHandler.remove, previous)

        # Because otherwise we can't test for warnings in different tests
        warnings.simplefilter('always', UserWarning)

    def test_base_configure(self):
        mg = Dailymg(self.directory)
        mg.configure()

        assert os.path.isdir(os.path.join(self.directory, '.dailymg'))
        assert os.path.isdir(os.path.join(self.directory, '.dailymg',
                                          'metadata'))

        assert mg.days == Dailymg.days
        assert mg.per_day == Dailymg.per_day
        assert mg.ratio == Dailymg.ratio
        assert mg.ratio_delta == Dailymg.ratio_delta

    def test_metadata_not_found(self):
        mg = Dailymg(self.directory)
        mg.configure()

        with warnings.catch_warnings(record=True) as w:
            assert mg.get_day_metadata(datetime(2015, 1, 1)) is None

        assert len(w) == 1
        assert 'Not found' in str(w[0].message)

    @freeze_time('2015-01-03')
    def test_metadata_found(self):
        mg = Dailymg(self.directory)
        mg.configure()
        mg.days = 2

        # x = mg.get_day_metadata(datetime(2015, 1, 2))
        print(mg.get_photos())
