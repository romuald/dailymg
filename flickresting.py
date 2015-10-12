# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 et ai
from __future__ import unicode_literals, absolute_import

import os
import sys
import gzip
import json
import os.path
import urllib2

from time import sleep
from pprint import pprint
from urlparse  import urlparse
from datetime import datetime, timedelta
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from multiprocessing.dummy import Pool

CONFIG_TEMPLATE = """
; Where the pictures will be downloaded
target-directory: ~/flickresting/
; How many days of photos shall be kept
days: 20
; Maximum number of photos to keep per day
max-per-day: 50

; Picture ratio to download, and percentage of tolerance (plus or minus x %)
ratio: 1.6
ratio-tolerance: 8%

"""

BASE_URL = 'http://flickr.chivil.com/interesting/'
TARGET = './photos/'
START_DATE = datetime.utcnow() - timedelta(days=1)
RATIO = 2560 / 1600.0
RATIO_DELTA = 0.05
DAYS = 20
MAX = 50
POOL_SIZE = 4


def b58encode(value):
    chars = '123456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ'
    base = len(chars) # let's not bother hard-coding
    encoded = ''
    while value >= base:
        div, mod = divmod(value, base)
        encoded = chars[mod] + encoded # add to left
        value = div
    encoded = chars[value] + encoded # most significant remainder
    return encoded

def get_metadata(day):
    """Fetch JSON data for a given day"""
    path = os.path.join(TARGET, '.cache')
    if not os.path.isdir(path):
        os.mkdir(path)
    filename = day.strftime('%Y-%m-%d.json')
    filepath = os.path.join(path, filename)
    if os.path.isfile(filepath):
        with file(filepath) as cachefile:
            return json.load(cachefile)

    url = BASE_URL + filename
    req = urllib2.Request(url)
    req.add_header('Accept-Encoding', 'gzip')
    try:
        res = urllib2.urlopen(req)
    except urllib2.HTTPError as err:
        print '%s - %d' % (url, err.code)
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
    return abs(RATIO - float(photo['ratio'])) < RATIO * RATIO_DELTA


def store_photo(photo):
    """Fetch a photo from flickr to storage"""
    url = photo['url']
    parts = (photo['date'].replace('-', ''),  # day
             b58encode(int(photo['id'])), # short id
             urlparse(url).path.split('.')[-1]) # file extension
    filename = '%s-%s.%s' % parts

    assert '..' not in filename

    filepath = os.path.join(TARGET, filename)
    if os.path.isfile(filepath):
        photo['done'] = True
        return photo

    # not thread-safe?
    source = urllib2.urlopen(url)
    contents = source.read()

    destination = open(filepath, 'w+')
    destination.write(contents)
    destination.close()
    photo['done'] = True



def main():
    date = START_DATE
    to_fetch = []
    for _ in xrange(DAYS):
        date -= timedelta(days=1)
        data = get_metadata(date)
        if data is None:
            continue

        photos = []
        for photo in data['photos']:
            if ratio_ok(photo):
                photo['date'] = data['date']
                photos.append(photo)

        print "%s %d photos matching %.1f +/-%d%% ratio " % (
            date.strftime('%Y-%m-%d'), len(photos), RATIO, RATIO_DELTA * 100)

        to_fetch.extend(photos[:MAX])

    print "%d photos to fetch" % len(to_fetch)

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


if __name__ == '__main__':
    main()
