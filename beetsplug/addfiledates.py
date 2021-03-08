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

"""Adds Windows 'Created On' and 'Modified On' dates to the item metadata of importing files.
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
from beets.ui.commands import PromptChoice
from beets.library import Item, Album
import six


PLUGIN = 'addwindowsfiledates'


class AddWindowsFileDatesPlugin(BeetsPlugin):
    """Adds Windows 'Created On' and 'Modified On' dates to the item metadata of importing files.""
    """
    def __init__(self):
        super(AddWindowsFileDatesPlugin, self).__init__()
        self.register_listener('item_copied', self.add_dates)

    def add_dates(self, item, source, destination):
        item.original_file_created_date = os.path.getctime(source)
        item.original_file_modified_date = os.path.getmtime(source)
            