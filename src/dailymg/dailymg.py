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
from urlparse import urlparse
from datetime import datetime, timedelta
from ConfigParser import SafeConfigParser

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from multiprocessing.dummy import Pool

from .blacklist import Blacklist


CONFIG_TEMPLATE = """
[dailymg]
; How many days of photos shall be kept
days: %(days)d
; Maximum number of photos to keep per day
per_day: %(per_day)d

; Picture ratio to download, and percentage of tolerance (plus or minus x %%)
ratio: %(ratio).2f
ratio_delta: %(ratio_delta).2f
""".lstrip()

BASE_URL = 'http://dailymg.chivil.com/interesting/'
TARGET = './photos/'

POOL_SIZE = 4
ICHARS = ('[=--]', '[-=-]', '[--=]', '[-=-]')
CLEAR = '\r\033[2K'


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('target', help='Directory where to download photos')

    res, _ = parser.parse_known_args()

    dailymg = Dailymg(res.target)
    dailymg.configure()

    parser.add_argument('-d', dest='days', type=int, default=dailymg.days,
                        help='Number of days to fetch')
    parser.add_argument('-n', dest='per_day', type=int,
                        default=dailymg.per_day,
                        help='Number of photos to download per day')
    parser.add_argument('-r', dest='ratio', default=dailymg.ratio,
                        help='Image ratio to match')
    parser.add_argument('-t', dest='ratio_delta', default=dailymg.ratio_delta,
                        type=float, help='Image ratio tolerance')

    res = parser.parse_args()

    dailymg.days = res.days
    dailymg.per_day = res.per_day
    dailymg.ratio = res.ratio
    dailymg.ratio_delta = res.ratio_delta

    dailymg.start()


def store_photo_url(path, url):
    """
    Optionally set the URL metadata for this photo (MacOS only)
    """
    try:
        libc = ctypes.cdll.LoadLibrary('libc.dylib')
        setxattr = libc.setxattr
    except (OSError, AttributeError) as err:
        # print "fail", err
        return

    path = path.encode('utf-8')
    url = url.encode('utf-8')

    setxattr(path, b'com.apple.metadata:kMDItemWhereFroms',
             url, len(url), 0, 0)


class Dailymg(object):
    ratio = 1.66
    ratio_delta = 0.05
    days = 60
    per_day = 5

    def __init__(self, target):
        self.target = target
        self.datadir = os.path.join(self.target, '.dailymg')
        self.metadata = None
        self.blacklist = Blacklist()
        self.start_date = datetime.utcnow() - timedelta(days=1)

    def configure(self):
        if not os.path.isdir(self.datadir):
            os.mkdir(self.datadir)

        mddir = os.path.join(self.datadir, 'metadata')
        if not os.path.isdir(mddir):
            os.mkdir(mddir)

        confpath = os.path.join(self.datadir, 'config.ini')
        if os.path.exists(confpath):
            parser = SafeConfigParser(allow_no_value=True)
            parser.read(confpath)

            def get_option(name, default):
                if parser.has_option('dailymg', name):
                    return parser.get('dailymg', name)
                return default
            self.days = int(get_option('days', self.days))
            self.per_day = int(get_option('per_day', self.per_day))
            self.ratio = float(get_option('ratio', self.ratio))
            self.ratio_delta = float(get_option('ratio_delta',
                                                self.ratio_delta))
        elif sys.stdin.isatty():
            try:
                self.interactive_configure(confpath)
            except KeyboardInterrupt:
                sys.exit(1)

    def interactive_configure(self, confpath):
        print('First run configuration')

        def get_number(question, default, format_='%d', type_=int,
                       valid=(0, 999)):
            while True:
                ret = raw_input(question + (' [%s] ' % format_) % default)

                if str(ret) == b'':
                    return default
                try:
                    ret = type_(ret)
                    if valid[0] < ret < valid[1]:
                        return ret
                except ValueError:
                    continue

        self.per_day = get_number('Number of photos to download per day',
                                  self.per_day)
        self.days = get_number('Number of days to fetch', self.days)
        self.ratio = get_number('Image ratio to match', self.ratio, '%.2f',
                                float, (0.09, 1.99))

        dd = {k: getattr(self, k) for k in dir(self)}
        try:
            with open(confpath, 'w+') as config:
                config.write(CONFIG_TEMPLATE % dd)
        except:
            if os.path.exists(confpath):
                os.remove(confpath)
            raise

    def get_day_metadata(self, day):
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
        # not thread-safe?
        source = urllib2.urlopen(photo.url)

        if 'photo_unavailable' in source.url:
            # pdb.set_trace()
            self.blacklist.add(photo)
            photo.done = True
            return

        contents = source.read()

        destination = open(photo.path, 'w+')
        destination.write(contents)
        destination.close()

        store_photo_url(photo.path, photo.url)

        photo.done = True

    def remove_expired(self):
        # Remove photos matching the photo pattern that aren't in the list of
        # photos we should have.
        # This is done to avoid an "infinite" fetch cycle when configuration
        # change between runs
        photo_re = re.compile('^[0-9]+-[a-zA-Z0-9]+\.[a-zA-Z0-9]+$')
        cache_re = re.compile('^[-0-9]{10}\.json\.gz$')

        current = set(name for name in os.listdir(self.target)
                      if photo_re.match(name))
        to_keep = set(photo.filename for photo in self.get_photos())
        to_remove = current - to_keep

        for photo in to_remove:
            os.unlink(os.path.join(self.target, photo))
        print "Deleted %d old photos" % len(to_remove)

        # Clear cache too
        to_keep = self.days
        cachedir = os.path.join(self.datadir, 'metadata')
        tmp = os.listdir(cachedir)
        cachefiles = [name for name in tmp if cache_re.match(name)]
        cachefiles.sort(reverse=True)
        to_remove = cachefiles[to_keep:]
        for cachefile in to_remove:
            os.unlink(os.path.join(cachedir, cachefile))
        print "Deleted %d old cache files" % len(to_remove)

    def get_photos(self):
        if self.metadata is None:
            self.metadata = self._fetch_metadata()

        ret = []
        for data in self.metadata:
            if data is None:
                continue

            photos = []
            for photo in data['photos']:
                photo = Photo(self, photo)
                if photo.ratio_ok and photo not in self.blacklist:
                    photo.date = data['date']
                    photos.append(photo)

            ret.extend(photos[:self.per_day])

        return ret

    def _fetch_metadata(self):
        iprogress = cycle(ICHARS)

        def progress():
            sys.stderr.write(CLEAR + 'Fetching metadata %s' % next(iprogress))
            sys.stderr.flush()

        pool = Pool(POOL_SIZE)

        todo = [self.start_date - timedelta(days=i) for i in range(self.days)]

        metadata = pool.map_async(self.get_day_metadata, todo)
        while not metadata.ready():
            progress()
            sleep(.1)

        sys.stderr.write(CLEAR + 'Fetching metadata [ * ]\n')
        sys.stderr.flush()

        return metadata.get()

    def start(self):
        self.blacklist.load(self.datadir)

        print 'Will fetch %d photo(s) per day for the last %d days' % \
            (self.per_day, self.days)


        to_fetch = self.get_photos()

        # XXX optim listdir
        to_fetch = [photo for photo in to_fetch
                    if not os.path.exists(photo.path)]

        print '%d photos to fetch' % len(to_fetch)

        def progress():
            count = len([_ for _ in to_fetch if _.done])
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

        if not res.successful():
            res.get()

        self.remove_expired()

if __name__ == '__main__':
    main()
    # Dailymg(TARGET).start()
