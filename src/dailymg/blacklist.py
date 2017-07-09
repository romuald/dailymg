# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 et ai
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import re
import json
import os.path


class Blacklist(object):
    maxsize = 5000

    def __init__(self):
        self.list = []

    def load(self, datadir):
        self.storepath = os.path.join(datadir, 'blacklist.json')

        try:
            with open(self.storepath) as blfile:
                self.list = json.load(blfile)
        except Exception:
            pass

    def add(self, photo):
        self.list.append(photo.id)

    def add_from_command_line(self, arguments):
        """
        Add to blacklist ids from a list of paths
        Ignores missing / invalid paths

        """
        base58 = '123456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ'
        pattern = re.compile('^[0-9]{8}-([%s]+)\.[^.]+$' % base58)

        for path in arguments:
            if not os.path.isfile(path):
                continue

            filename = os.path.basename(path)
            match = pattern.search(filename)
            if not match:
                return

            id_ =  match.group(1)
            if id_ not in self.list:
                self.list.append(id_)

            os.unlink(path)


    def __contains__(self, photo):
        return photo.id in self.list

    def save(self):
        del self.list[self.maxsize:]

        with open(self.storepath, 'w+') as blfile:
            json.dump(self.list, blfile)
