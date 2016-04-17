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

# init in main()
BLACKLIST = None
DATADIR = None


class Blacklist(object):
    maxsize = 5000

    def __init__(self):
        self.storepath = os.path.join(DATADIR, 'blacklist.json')

        try:
            with file(self.storepath) as blfile:
                self.list = json.load(blfile)
        except Exception:
            self.list = []

    def add(self, photo):
        self.list.append(photo['id'])

    def __contains__(self, photo):
        return photo['id'] in self.list

    def save(self):
        del self.list[self.maxsize:]

        with file(self.storepath, 'w+') as blfile:
            json.dump(self.list, blfile)


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


def get_metadata(day):
    """Fetch JSON data for a given day"""

    filename = day.strftime('%Y-%m-%d.json')
    filepath = os.path.join(DATADIR, 'metadata', filename)
    if os.path.isfile(filepath):
        with file(filepath) as cachefile:
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

    with file(filepath, 'w+') as cachefile:
        cachefile.write(data)
    return json.loads(data)


def ratio_ok(photo):
    return (
        RATIO - RATIO * RATIO_DELTA <
        float(photo['ratio']) <
        RATIO + RATIO * RATIO_DELTA)


def store_photo(photo):
    """Fetch a photo from flickr to storage"""
    url = photo['url']

    parts = (photo['date'].replace('-', ''),  # day
             photo['id'], # short id
             urlparse(url).path.split('.')[-1]) # file extension
    filename = '%s-%s.%s' % parts

    assert '..' not in filename

    filepath = os.path.join(TARGET, filename)
    if os.path.isfile(filepath):
        photo['done'] = True
        return photo

    # not thread-safe?
    source = urllib2.urlopen(url)
    
    if 'photo_unavailable' in source.url:
        # pdb.set_trace()
        BLACKLIST.add(photo)
        photo['done'] = True
        return

    contents = source.read()

    destination = open(filepath, 'w+')
    destination.write(contents)
    destination.close()

    store_photo_url(filepath, url)

    photo['done'] = True

def remove_expired():
    # XXX remove old cache files
    # Do not blindly remove photos of more than X days
    # Instead, keep N photos. In case we could not retrive some recent photos
    to_keep = DAYS * MAX  
    photo_re = re.compile('^[0-9]+-[a-zA-Z0-9]+\.[a-zA-Z0-9]+$')
    tmp = os.listdir(TARGET)
    photos = [name for name in tmp if photo_re.match(name)]
    photos.sort(reverse=True)

    to_remove = photos[to_keep:]
    for photo in to_remove:
        os.unlink(os.path.join(TARGET, photo))
    print "Deleted %d old photos" % len(to_remove)


ICHARS = ('[=--]', '[-=-]', '[--=]', '[-=-]')
CLEAR = '\r\033[2K'

def main():
    global BLACKLIST, DATADIR

    date = START_DATE
    to_fetch = []
    done, todo = 0, DAYS
    iprogress = cycle(ICHARS)

    def progress():
        sys.stderr.write(CLEAR + 'Fetching metadata %s' % next(iprogress))
        sys.stderr.flush()

    DATADIR = os.path.join(TARGET, '.dailymg')
    if not os.path.isdir(DATADIR):
        os.mkdir(DATADIR)

    mddir = os.path.join(DATADIR, 'metadata')
    if not os.path.isdir(mddir):
        os.mkdir(mddir)

    BLACKLIST = Blacklist()

    pool = Pool(POOL_SIZE)

    todo = [date - timedelta(days=i) for i in range(DAYS)]
    metadata = pool.map_async(get_metadata, todo, chunksize=1)
    while not metadata.ready():
        progress()
        sleep(.1)
    sys.stderr.write(CLEAR + 'Fetching metadata [ * ]\n')
    sys.stderr.flush()

    for data in metadata.get(): # while False:  # for _ in xrange(DAYS):
        # date -= timedelta(days=1)
        # data = get_metadata(date)
        if data is None:
            continue

        photos = []
        for photo in data['photos']:
            if ratio_ok(photo) and photo not in BLACKLIST:
                photo['date'] = data['date']
                photos.append(photo)

        # print "%s %d photos matching %.1f +/-%d%% ratio " % (
        #     date.strftime('%Y-%m-%d'), len(photos), RATIO, RATIO_DELTA * 100)

        to_fetch.extend(photos[:MAX])

    print >> sys.stderr, ''

    #existing = set(os.listdir(TARGET))
    #to_fetch = [photo for photo in to_fetch if photo]


    print '%d photos to fetch' % len(to_fetch)

    def progress():
        count = len([_ for _ in to_fetch if 'done' in _])
        dd = '%%%dd' % len(str(len(to_fetch)))
        template = 'Fetching %s/%s photos' % (dd, dd)
        sys.stderr.write('\r' + template % (count, len(to_fetch)))
        sys.stderr.flush()

    pool = Pool(POOL_SIZE)

    res = pool.map_async(store_photo, to_fetch)

    while not res.ready():
        progress()
        sleep(.1)
    progress()
    print ''

    BLACKLIST.save()

    remove_expired()


if __name__ == '__main__':
    main()
