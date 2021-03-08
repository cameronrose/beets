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
from beets.ui.commands import PromptChoice
from beets.library import Item, Album
import six


PLUGIN = 'multisource'


class MultiSourcePlugin(BeetsPlugin):
    """Tag imports with metadata from multiple data sources""
    """
    def __init__(self):
        super(MultiSourcePlugin, self).__init__()
        self.register_listener('before_choose_candidate_event', self.prompt)

    def prompt(self, session, task):
        
        return [PromptChoice('p', 'Enter number of other source metadata choice here', self.applychoice)]


    def applychoice(self, session, task):
        items = task.imported_items()
        if len(items):
            pass
            