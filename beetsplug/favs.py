# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Pedro Silva.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Tag favourite files in album import.
"""
from __future__ import division, absolute_import, print_function

import os
import shlex
import sys

from beets import config
from beets.plugins import BeetsPlugin
from beets.ui import decargs, print_, Subcommand, UserError
from beets.util import command_output, displayable_path, subprocess, \
    bytestring_path, MoveOperation
from beets.library import Item, Album
import six


PLUGIN = 'favs'


class FavsPlugin(BeetsPlugin):
    """Favourite files""
    """
    def __init__(self):
        super(FavsPlugin, self).__init__()
        self.register_listener('item_copied', self.added)
        self.register_listener('item_moved', self.added)
        self.register_listener('item_linked', self.added)
        self.register_listener('item_hardlinked', self.added)

    def added(self, item, source, destination):
        if 'favs' in config['import'] :
            self.favs = config['import']['favs'].as_str_seq()
            if len(self.favs) > 0:
                path = source.decode(sys.getfilesystemencoding())
                filename = os.path.basename(path)
                
                for fav_path in self.favs:
                    fav_filename = os.path.basename(fav_path)

                    if filename == fav_filename :
                        item.is_fav = True
                        item.store()
                