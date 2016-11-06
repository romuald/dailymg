from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import os
import os.path
import tempfile
import shutil
import unittest

from datetime import datetime

import mock

from dailymg import Dailymg


def side_request(arg):
    print("REQUEST FOR:", arg)
    ret = mock.MagicMock(url=arg)

    return ret


def side_open(arg):
    print("REQUEST READ FOR:", arg)

    ret = mock.MagicMock()
    ret.read.side_effect = ['{"photos": [], "url": "%s"}' % arg.url]
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
        def side1(arg):
            print("REQUEST FOR:", arg)
            ret = mock.MagicMock(url=arg)
            # ret.read.side_effect = '{"photos": []}'
            return ret

        def side2(arg):
            print("REQUEST READ FOR:", arg.url)
            ret = mock.MagicMock()
            ret.read.side_effect = ['{"photos": [], "url": "%s"}' % arg.url]
            return ret
            return '{"photos": []}'
        #m_request.side_effect = side1
        #m_urlopen.side_effect = side2
        # m_urlopen().read.side_effect = ['{"photos": []}'] * 80

        mg = Dailymg(self.directory)
        mg.configure()
        mg.days = 2
        print(mg.get_day_metadata(datetime(2015, 1, 1)))
        #print(mg.get_photos())
