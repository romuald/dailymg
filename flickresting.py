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

BASE_URL = 'http://flickr.chivil.com/interesting/'
TARGET = './flickr/'
START_DATE = datetime.utcnow() - timedelta(days=1)
RATIO = 2560 / 1600.0
RATIO_DELTA = 0.05
DAYS = 4
POOL_SIZE = 4

def get_metadata(day):
    path = os.path.join(TARGET, 'cache')
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

date = START_DATE
to_fetch = []
for _ in xrange(DAYS):
    date -= timedelta(days=1)
    data = get_metadata(date)
    if data is None:
        continue
    photos = filter(ratio_ok, data['photos'])

    print "%s %d photos matching %.1f +/-%d%% ratio " % (
        date.strftime('%Y-%m-%d'), len(photos), RATIO, RATIO_DELTA * 100)

    to_fetch.extend(photos)

print "%d photos to fetch" % len(to_fetch)


def store_photo(photo):
    url = photo['url']
    filename = urlparse(url).path.split('/')[-1]
    filepath = os.path.join(TARGET, filename)

    if os.path.isfile(filepath):
        photo['done'] = True
        return photo

    # thread-safe?
    source = urllib2.urlopen(url)
    contents = source.read()

    destination = open(filepath, 'w+')
    destination.write(contents)
    destination.close()
    photo['done'] = True


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
print >> sys.stderr, ''

photos = []
for i, photo in photos:
    url = url_template % {
        'id' : photo['id'],
        'farm' : photo['farm'],
        'server' : photo['server'],
        'secret' : photo['secret'],
    }
    photo['ratio'] = get_ratio(photo)
    pprint(photo)
    continue
    if i == 5:
        break
    
    
    
    if os.path.isfile(filepath):
        skipped += 1
        continue
    continue
    source = urllib2.urlopen(url)
    contents = source.read()

    if contents[:3] == "GIF":
        source.close()
        _404 += 1
        continue

    destination = open(filepath, 'w+')
    destination.write(contents)
    destination.close()
    
    sys.stdout.write('.')
    sys.stdout.flush()

