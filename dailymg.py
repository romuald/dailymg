# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 et ai
from __future__ import unicode_literals, absolute_import

import os
import re
import sys
import gzip
import json
import ctypes
import os.path
import urllib2
import argparse

from time import sleep
from pprint import pprint
from itertools import cycle
from urlparse  import urlparse
from datetime import datetime, timedelta

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from multiprocessing.dummy import Pool

# UNUSED
CONFIG_TEMPLATE = """
; Where the pictures will be downloaded
target-directory: ~/flickresting/
; How many days of photos shall be kept
days: 30
; Maximum number of photos to keep per day
max-per-day: 5

; Picture ratio to download, and percentage of tolerance (plus or minus x %)
ratio: 1.6
ratio-tolerance: 0.05

"""

BASE_URL = 'http://dailymg.chivil.com/interesting/'
TARGET = './photos/'
START_DATE = datetime.utcnow() - timedelta(days=1)
RATIO = 2560 / 1600.0
RATIO_DELTA = 0.05
DAYS = 60
MAX = 5
POOL_SIZE = 4

ICHARS = ('[=--]', '[-=-]', '[--=]', '[-=-]')
CLEAR = '\r\033[2K'


class Blacklist(object):
    maxsize = 5000

    def __init__(self):
        self.list = []

    def load(self, datadir):
        self.storepath = os.path.join(datadir, 'blacklist.json')

        try:
            with file(self.storepath) as blfile:
                self.list = json.load(blfile)
        except Exception:
            pass

    def add(self, photo):
        self.list.append(photo['id'])

    def __contains__(self, photo):
        return photo['id'] in self.list

    def save(self):
        del self.list[self.maxsize:]

        with file(self.storepath, 'w+') as blfile:
            json.dump(self.list, blfile)


def main():
    """unused yet"""
    parser = argparse.ArgumentParser()
    parser.add_argument('target', help='Directory where to download photos')
    parser.add_argument('-d', dest='days', type=int, default=10,
                        help='Number of days to fetch')
    parser.add_argument('-n', dest='number', type=int, default=4,
                        help='Number of photos to download per day')
    parser.add_argument('-r', dest='ratio', default=1.66,
                        help='Image ratio to match')
    parser.add_argument('-t', dest='tolerance', default=0.05,
                        help='Image ratio tolerance')

    print parser.parse_args()

class Dailymg(object):
    def __init__(self, target):
        self.target = target
        self.datadir = os.path.join(self.target, '.dailymg')
        self.blacklist = Blacklist()

        self.pool_size = POOL_SIZE
        self.start_date = START_DATE
        self.days = DAYS
        self.per_day = MAX
        self.ratio = RATIO
        self.ratio_delta = RATIO_DELTA

    def ratio_ok(self, photo):
        return (
            self.ratio - self.ratio * self.ratio_delta <
            float(photo['ratio']) <
            self.ratio + self.ratio * self.ratio_delta)
        

    def get_metadata(self, day):
        """Fetch JSON data for a given day"""

        filename = day.strftime('%Y-%m-%d.json')
        filepath = os.path.join(self.datadir, 'metadata', filename)
        zfilepath = filepath + '.gz'
        if os.path.isfile(zfilepath):
            with gzip.GzipFile(zfilepath) as cachefile:
                return json.load(cachefile)

        url = BASE_URL + filename
        req = urllib2.Request(url)
        req.add_header('Accept-Encoding', 'gzip')
        try:
            res = urllib2.urlopen(req)
        except Exception as err:
            # print '%s - %d' % (url, err.code)
            return None

        if res.info().get('Content-Encoding') == 'gzip':
            buf = StringIO(res.read())
            f = gzip.GzipFile(fileobj=buf)
            data = f.read()
        else:
            data = res.read()

        with gzip.GzipFile(zfilepath, 'w+') as cachefile:
            buf = StringIO(data)

            cachefile.write(data)
        return json.loads(data)

    def store_photo(self, photo):
        """Fetch a photo from flickr to storage"""
        url = photo['url']

        parts = (photo['date'].replace('-', ''),  # day
                 photo['id'], # short id
                 urlparse(url).path.split('.')[-1]) # file extension
        filename = '%s-%s.%s' % parts

        assert '..' not in filename

        filepath = os.path.join(self.target, filename)
        if os.path.isfile(filepath):
            photo['done'] = True
            return photo

        # not thread-safe?
        source = urllib2.urlopen(url)
        
        if 'photo_unavailable' in source.url:
            # pdb.set_trace()
            self.blacklist.add(photo)
            photo['done'] = True
            return

        contents = source.read()

        destination = open(filepath, 'w+')
        destination.write(contents)
        destination.close()

        store_photo_url(filepath, url)

        photo['done'] = True

    def remove_expired(self):
        # XXX remove old cache files

        # Do not blindly remove photos of more than X days
        # Instead, keep N photos.
        # In case we could not retrive some recent photos
        to_keep = self.days * self.per_day  
        photo_re = re.compile('^[0-9]+-[a-zA-Z0-9]+\.[a-zA-Z0-9]+$')
        tmp = os.listdir(self.target)
        photos = [name for name in tmp if photo_re.match(name)]
        photos.sort(reverse=True)

        to_remove = photos[to_keep:]
        for photo in to_remove:
            os.unlink(os.path.join(self.target, photo))
        print "Deleted %d old photos" % len(to_remove)


    def start(self):
        if not os.path.isdir(self.datadir):
            os.mkdir(self.datadir)

        mddir = os.path.join(self.datadir, 'metadata')
        if not os.path.isdir(mddir):
            os.mkdir(mddir)

        self.blacklist.load(self.datadir)

        iprogress = cycle(ICHARS)
        def progress():
            sys.stderr.write(CLEAR + 'Fetching metadata %s' % next(iprogress))
            sys.stderr.flush()

        pool = Pool(POOL_SIZE)

        todo = [self.start_date - timedelta(days=i) for i in range(self.days)]

        metadata = pool.map_async(self.get_metadata, todo)
        while not metadata.ready():
            progress()
            sleep(.1)

        sys.stderr.write(CLEAR + 'Fetching metadata [ * ]\n')
        sys.stderr.flush()

        to_fetch = []
        for data in metadata.get():
            if data is None:
                continue

            photos = []
            for photo in data['photos']:
                if self.ratio_ok(photo) and photo not in self.blacklist:
                    photo['date'] = data['date']
                    photos.append(photo)

            # print "%s %d photos matching %.1f +/-%d%% ratio " % (
            #     date.strftime('%Y-%m-%d'), len(photos), RATIO, RATIO_DELTA * 100)

            to_fetch.extend(photos[:self.per_day])

        print >> sys.stderr, ''

        print '%d photos to fetch' % len(to_fetch)

        def progress():
            count = len([_ for _ in to_fetch if 'done' in _])
            dd = '%%%dd' % len(str(len(to_fetch)))
            template = 'Fetching %s/%s photos' % (dd, dd)
            sys.stderr.write('\r' + template % (count, len(to_fetch)))
            sys.stderr.flush()

        pool = Pool(POOL_SIZE)

        res = pool.map_async(self.store_photo, to_fetch)

        while not res.ready():
            progress()
            sleep(.1)
        progress()
        print >> sys.stderr, ''

        self.blacklist.save()

        self.remove_expired()

if __name__ == '__main__':
    Dailymg(TARGET).start()

