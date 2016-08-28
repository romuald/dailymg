# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 et ai
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os.path

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse


class Photo(object):
    def __init__(self, dailymg, photo):
        self.id = photo['id']
        self.url = photo['url']
        self.date = photo.get('date')
        self.ratio = float(photo['ratio'])
        self.done = False  # Used for download progress check only
        self.mg = dailymg

    @property
    def ratio_ok(self):
        return (
            self.mg.ratio - self.mg.ratio * self.mg.ratio_delta <
            self.ratio <
            self.mg.ratio + self.mg.ratio * self.mg.ratio_delta)

    @property
    def filename(self):
        assert self.date

        url = self.url

        parts = (self.date.replace('-', ''),         # day
                 self.id,                            # short id
                 urlparse(url).path.split('.')[-1])  # file extension
        filename = '%s-%s.%s' % parts

        assert '..' not in filename

        return filename

    @property
    def path(self):
        """The local file path"""
        return os.path.join(self.mg.target, self.filename)

    def __repr__(self):
        return '<Photo %s (%s)>' % (self.id, self.date)
