# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

"""Adds Soundcloud playlist and track search support to the autotagger. Requires the
python-soundcloud library.
"""
from __future__ import division, absolute_import, print_function

import beets.ui
from beets import config
from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.plugins import MetadataSourcePlugin, BeetsPlugin, get_distance
import confuse
from discogs_client import Release, Master, Client
from discogs_client.exceptions import DiscogsAPIError
from requests.exceptions import ConnectionError
from six.moves import http_client
import functools
import beets
import re
import time
import json
import socket
import os
import traceback
from string import ascii_lowercase
import soundcloud
from requests.exceptions import HTTPError

USER_AGENT = u'beets/{0} +https://beets.io/'.format(beets.__version__)
CLIENT_ID = 'T11SSWT7phP76J1tU4T6x0NMmXxVnYWx'

# Exceptions that soundcloud library should really handle but does not.
CONNECTION_ERRORS = (ConnectionError, socket.error, http_client.HTTPException,
                     ValueError,  # JSON decoding raises a ValueError.
                     DiscogsAPIError)


class SoundcloudPlugin(BeetsPlugin):

    def __init__(self):
        super(SoundcloudPlugin, self).__init__()
        self.config.add({
            'source_weight': 0.1,
        })
        self.soundcloud_client = None
        self.register_listener('import_begin', self.setup)

        # if self.config['collection']['folderindex'].as_number():
        #     self.register_listener('album_imported', self.album_added)

        self.rate_limit_per_minute = 25
        self.last_request_timestamp = 0

    def setup(self, session=None):
        """Create the `soundcloud_client` field.
        """

        self.soundcloud_client = soundcloud.Client(client_id=CLIENT_ID)
    

    def album_distance(self, items, album_info, mapping):
        """Returns the album distance.
        """
        return get_distance(
            data_source='Soundcloud',
            info=album_info,
            config=self.config
        )

    def track_distance(self, item, track_info):
        """Returns the track distance.
        """
        return get_distance(
            data_source='Soundcloud',
            info=track_info,
            config=self.config
        )

    def candidates(self, items, artist, album, va_likely, extra_tags=None):
        """Returns a list of AlbumInfo objects for Soundcloud search results
        matching an album and artist (if not various).
        """
        if not self.soundcloud_client:
            return

        if album == 'Untitled':
            album = ''
        if va_likely:
            query = album
        else:
            query = '%s %s' % (artist, album)
        try:
            return self.get_albums(query, artist, album, items)
        except DiscogsAPIError as e:
            self._log.debug(u'API Error: {0} (query: {1})', e, query)
            # if e.status_code == 401:
            #     self.reset_auth()
            #     return self.candidates(items, artist, album, va_likely)
            # else:
            #     return []
            return []
        except CONNECTION_ERRORS:
            self._log.debug(u'Connection error in album search', exc_info=True)
            return []

    # def album_for_id(self, album_id):
    #     """Fetches an album by its Discogs ID and returns an AlbumInfo object
    #     or None if the album is not found.
    #     """
    #     if not self.discogs_client:
    #         return

    #     self._log.debug(u'Searching for release {0}', album_id)
    #     # Discogs-IDs are simple integers. We only look for those at the end
    #     # of an input string as to avoid confusion with other metadata plugins.
    #     # An optional bracket can follow the integer, as this is how discogs
    #     # displays the release ID on its webpage.
    #     match = re.search(r'(^|\[*r|discogs\.com/.+/release/)(\d+)($|\])',
    #                       album_id)
    #     if not match:
    #         return None
    #     result = Release(self.discogs_client, {'id': int(match.group(2))})
    #     # Try to obtain title to verify that we indeed have a valid Release
    #     try:
    #         getattr(result, 'title')
    #     except DiscogsAPIError as e:
    #         if e.status_code != 404:
    #             self._log.debug(u'API Error: {0} (query: {1})', e,
    #                             result.data['resource_url'])
    #             if e.status_code == 401:
    #                 self.reset_auth()
    #                 return self.album_for_id(album_id)
    #         return None
    #     except CONNECTION_ERRORS:
    #         self._log.debug(u'Connection error in album lookup', exc_info=True)
    #         return None
    #     return self.get_album_info(result)

    def get_albums(self, query, artist, album, items):
        """Returns a list of AlbumInfo objects for a Soundcloud search query.
        """
        # Strip non-word characters from query. Things like "!" and "-" can
        # cause a query to return no results, even if they match the artist or
        # album title. Use `re.UNICODE` flag to avoid stripping non-english
        # word characters.
        # FIXME: Encode as ASCII to work around a bug:
        # https://github.com/beetbox/beets/issues/1051
        # When the library is fixed, we should encode as UTF-8.
        query = re.sub(r'(?u)\W+', ' ', query).encode('ascii', "replace")
        # Strip medium information from query, Things like "CD1" and "disk 1"
        # can also negate an otherwise positive result.
        query = re.sub(br'(?i)\b(CD|disc)\s*\d+', b'', query)
        query = re.sub(br'(?i)\b(EP)\s*', b'', query)
        query_str = query.decode("utf-8") 
        # query_str += '&limit=20'
        #query = query.decode("utf-8")
        
        try:
            result = self.soundcloud_client.get('/search',q=query_str)
        except HTTPError as e:
            self._log.debug(u'Connection error in album lookup', exc_info=True)
            return []


        return [album for album in map(functools.partial(self.get_album_info, artist=artist, album=album, items=items), result.collection)
                if album]

    # def get_master_year(self, master_id):
    #     """Fetches a master release given its Discogs ID and returns its year
    #     or None if the master release is not found.
    #     """
    #     self._log.debug(u'Searching for master release {0}', master_id)
    #     result = Master(self.discogs_client, {'id': master_id})

    #     self.request_start()
    #     try:
    #         year = result.fetch('year')
    #         self.request_finished()
    #         return year
    #     except DiscogsAPIError as e:
    #         if e.status_code != 404:
    #             self._log.debug(u'API Error: {0} (query: {1})', e,
    #                             result.data['resource_url'])
    #             if e.status_code == 401:
    #                 self.reset_auth()
    #                 return self.get_master_year(master_id)
    #         return None
    #     except CONNECTION_ERRORS:
    #         self._log.debug(u'Connection error in master release lookup',
    #                         exc_info=True)
    #         return None

    def get_album_info(self, result, artist, album, items):
        """Returns an AlbumInfo object for a discogs Release object.
        """
        if result.kind in ['playlist', 'album']:
            user = result.user.get('username')      
            tracks = list()
            for track_result in result.tracks:
                title = ''
                if hasattr(track_result, 'title'):
                    title = track_result.get('title')
                    title = re.sub('\(clip\)$', '', title, flags=re.IGNORECASE)
                    artist_remove_exp =  '^' + artist +  ' \- '
                    title = re.sub(artist_remove_exp, '', title, flags=re.IGNORECASE)
                track_number = result.tracks.index(track_result) + 1
                track = TrackInfo(
                    artist = artist,
                    album = album,
                    title = title.strip(),
                    index=track_number,
                    medium_index=track_number,
                    soundcloud_trackid = track_result.get('id'))
                tracks.append(track)
            
            return AlbumInfo(tracks,soundcloud_playlistid=result.id,
                            soundcloud_userid=result.user_id,
                            album=result.title,
                            artist=artist,
                            soundcloud_username=user,
                            data_source='Soundcloud') 

        if result.kind == 'track':
            user = result.user.get('username')    
            title = result.title
            title = re.sub('\(clip\)$', '', title, flags=re.IGNORECASE)
            artist_remove_exp =  '^' + artist +  ' \- '
            title = re.sub(artist_remove_exp, '', title, flags=re.IGNORECASE)
            tracks = self.get_tracks_from_comments(result, artist, album, items)

            return AlbumInfo(tracks,
                            soundcloud_userid=result.user_id,
                            album=result.title,
                            artist=artist,
                            soundcloud_username=user,
                            data_source='Soundcloud') 
        return None


    def get_comments(self, track_id):
        try:
            result = self.soundcloud_client.get('/tracks/' + str(track_id) + '/comments', threaded='1',filter_replies='0',limit='50')
        except HTTPError as e:
            self._log.debug(u'Connection error in album lookup', exc_info=True)
            return list()
        return result.collection

    def get_tracks_from_comments(self, track_result, artist, album, items):
        
        tracks = list()
        comments = self.get_comments(track_result.id)
        filtered_comments = self.get_track_names_from_comments(comments, track_result.user_id, items)

        if filtered_comments:
            for item in items:
                if item.track in filtered_comments:      
                    track = filtered_comments[item.track]              
                    tracks.append(TrackInfo(
                            artist = artist,
                            album = album,
                            title = track.body,
                            soundcloud_tracktimestamp = track.timestamp,
                            index=item.track,
                            medium_index=item.track,
                            soundcloud_trackid = track_result.id))
        return tracks

    def get_user_comments(self, comments, user_id):
        return list(
                filter(lambda x: x.user_id == user_id and x.timestamp != None, comments)
                )

    def get_track_names_from_comments(self, comments, user_id, items):    
        track_name_comments = {}
        user_comments = self.get_user_comments(comments, user_id)
        if user_comments is not None:
            user_comments.sort(key=self.get_comment_time)
            for item in items:
                
                for user_comment in user_comments:
                    if item.get('title') in user_comment.body:
                        user_comment.body = item.get('title')
                        track_name_comments[item.track] = user_comment

        return track_name_comments

    def get_comment_time(self, comment):
        return comment.timestamp

    def format(self, classification):
        if classification:
            return self.config['separator'].as_str() \
                .join(sorted(classification))
        else:
            return None

    def extract_release_id(self, uri):
        if uri:
            return uri.split("/")[-1]
        else:
            return None

    def get_tracks(self, tracklist):
        """Returns a list of TrackInfo objects for a discogs tracklist.
        """
        try:
            clean_tracklist = self.coalesce_tracks(tracklist)
        except Exception as exc:
            # FIXME: this is an extra precaution for making sure there are no
            # side effects after #2222. It should be removed after further
            # testing.
            self._log.debug(u'{}', traceback.format_exc())
            self._log.error(u'uncaught exception in coalesce_tracks: {}', exc)
            clean_tracklist = tracklist
        tracks = []
        index_tracks = {}
        index = 0
        # Distinct works and intra-work divisions, as defined by index tracks.
        divisions, next_divisions = [], []
        for track in clean_tracklist:
            # Only real tracks have `position`. Otherwise, it's an index track.
            if track['position']:
                index += 1
                if next_divisions:
                    # End of a block of index tracks: update the current
                    # divisions.
                    divisions += next_divisions
                    del next_divisions[:]
                track_info = self.get_track_info(track, index, divisions)
                track_info.track_alt = track['position']
                tracks.append(track_info)
            else:
                next_divisions.append(track['title'])
                # We expect new levels of division at the beginning of the
                # tracklist (and possibly elsewhere).
                try:
                    divisions.pop()
                except IndexError:
                    pass
                index_tracks[index + 1] = track['title']

        # Fix up medium and medium_index for each track. Discogs position is
        # unreliable, but tracks are in order.
        medium = None
        medium_count, index_count, side_count = 0, 0, 0
        sides_per_medium = 1

        # If a medium has two sides (ie. vinyl or cassette), each pair of
        # consecutive sides should belong to the same medium.
        if all([track.medium is not None for track in tracks]):
            m = sorted(set([track.medium.lower() for track in tracks]))
            # If all track.medium are single consecutive letters, assume it is
            # a 2-sided medium.
            if ''.join(m) in ascii_lowercase:
                sides_per_medium = 2

        for track in tracks:
            # Handle special case where a different medium does not indicate a
            # new disc, when there is no medium_index and the ordinal of medium
            # is not sequential. For example, I, II, III, IV, V. Assume these
            # are the track index, not the medium.
            # side_count is the number of mediums or medium sides (in the case
            # of two-sided mediums) that were seen before.
            medium_is_index = track.medium and not track.medium_index and (
                len(track.medium) != 1 or
                # Not within standard incremental medium values (A, B, C, ...).
                ord(track.medium) - 64 != side_count + 1
            )

            if not medium_is_index and medium != track.medium:
                side_count += 1
                if sides_per_medium == 2:
                    if side_count % sides_per_medium:
                        # Two-sided medium changed. Reset index_count.
                        index_count = 0
                        medium_count += 1
                else:
                    # Medium changed. Reset index_count.
                    medium_count += 1
                    index_count = 0
                medium = track.medium

            index_count += 1
            medium_count = 1 if medium_count == 0 else medium_count
            track.medium, track.medium_index = medium_count, index_count

        # Get `disctitle` from Discogs index tracks. Assume that an index track
        # before the first track of each medium is a disc title.
        for track in tracks:
            if track.medium_index == 1:
                if track.index in index_tracks:
                    disctitle = index_tracks[track.index]
                else:
                    disctitle = None
            track.disctitle = disctitle

        return tracks

    def coalesce_tracks(self, raw_tracklist):
        """Pre-process a tracklist, merging subtracks into a single track. The
        title for the merged track is the one from the previous index track,
        if present; otherwise it is a combination of the subtracks titles.
        """
        def add_merged_subtracks(tracklist, subtracks):
            """Modify `tracklist` in place, merging a list of `subtracks` into
            a single track into `tracklist`."""
            # Calculate position based on first subtrack, without subindex.
            idx, medium_idx, sub_idx = \
                self.get_track_index(subtracks[0]['position'])
            position = '%s%s' % (idx or '', medium_idx or '')

            if tracklist and not tracklist[-1]['position']:
                # Assume the previous index track contains the track title.
                if sub_idx:
                    # "Convert" the track title to a real track, discarding the
                    # subtracks assuming they are logical divisions of a
                    # physical track (12.2.9 Subtracks).
                    tracklist[-1]['position'] = position
                else:
                    # Promote the subtracks to real tracks, discarding the
                    # index track, assuming the subtracks are physical tracks.
                    index_track = tracklist.pop()
                    # Fix artists when they are specified on the index track.
                    if index_track.get('artists'):
                        for subtrack in subtracks:
                            if not subtrack.get('artists'):
                                subtrack['artists'] = index_track['artists']
                    tracklist.extend(subtracks)
            else:
                # Merge the subtracks, pick a title, and append the new track.
                track = subtracks[0].copy()
                track['title'] = ' / '.join([t['title'] for t in subtracks])
                tracklist.append(track)

        # Pre-process the tracklist, trying to identify subtracks.
        subtracks = []
        tracklist = []
        prev_subindex = ''
        for track in raw_tracklist:
            # Regular subtrack (track with subindex).
            if track['position']:
                _, _, subindex = self.get_track_index(track['position'])
                if subindex:
                    if subindex.rjust(len(raw_tracklist)) > prev_subindex:
                        # Subtrack still part of the current main track.
                        subtracks.append(track)
                    else:
                        # Subtrack part of a new group (..., 1.3, *2.1*, ...).
                        add_merged_subtracks(tracklist, subtracks)
                        subtracks = [track]
                    prev_subindex = subindex.rjust(len(raw_tracklist))
                    continue

            # Index track with nested sub_tracks.
            if not track['position'] and 'sub_tracks' in track:
                # Append the index track, assuming it contains the track title.
                tracklist.append(track)
                add_merged_subtracks(tracklist, track['sub_tracks'])
                continue

            # Regular track or index track without nested sub_tracks.
            if subtracks:
                add_merged_subtracks(tracklist, subtracks)
                subtracks = []
                prev_subindex = ''
            tracklist.append(track)

        # Merge and add the remaining subtracks, if any.
        if subtracks:
            add_merged_subtracks(tracklist, subtracks)

        return tracklist

    def get_track_info(self, track, index, divisions):
        """Returns a TrackInfo object for a discogs track.
        """
        title = track['title']
        if self.config['index_tracks']:
            prefix = ', '.join(divisions)
            title = ': '.join([prefix, title])
        track_id = None
        medium, medium_index, _ = self.get_track_index(track['position'])
        artist, artist_id = MetadataSourcePlugin.get_artist(
            track.get('artists', [])
        )
        length = self.get_track_length(track['duration'])
        return TrackInfo(title=title, track_id=track_id, artist=artist,
                         artist_id=artist_id, length=length, index=index,
                         medium=medium, medium_index=medium_index)

    def get_track_index(self, position):
        """Returns the medium, medium index and subtrack index for a discogs
        track position."""
        # Match the standard Discogs positions (12.2.9), which can have several
        # forms (1, 1-1, A1, A1.1, A1a, ...).
        match = re.match(
            r'^(.*?)'           # medium: everything before medium_index.
            r'(\d*?)'           # medium_index: a number at the end of
                                # `position`, except if followed by a subtrack
                                # index.
                                # subtrack_index: can only be matched if medium
                                # or medium_index have been matched, and can be
            r'((?<=\w)\.[\w]+'  # - a dot followed by a string (A.1, 2.A)
            r'|(?<=\d)[A-Z]+'   # - a string that follows a number (1A, B2a)
            r')?'
            r'$',
            position.upper()
        )

        if match:
            medium, index, subindex = match.groups()

            if subindex and subindex.startswith('.'):
                subindex = subindex[1:]
        else:
            self._log.debug(u'Invalid position: {0}', position)
            medium = index = subindex = None
        return medium or None, index or None, subindex or None

    def get_track_length(self, duration):
        """Returns the track length in seconds for a discogs duration.
        """
        try:
            length = time.strptime(duration, '%M:%S')
        except ValueError:
            return None
        return length.tm_min * 60 + length.tm_sec
