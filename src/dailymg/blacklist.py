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

    def __contains__(self, photo):
        return photo.id in self.list

    def save(self):
        del self.list[self.maxsize:]

        with open(self.storepath, 'w+') as blfile:
            json.dump(self.list, blfile)
