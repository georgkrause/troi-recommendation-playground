import requests
import ujson

from troi import Element, Artist, PipelineError, Recording, Playlist


class RecordingLookupElement(Element):
    '''
        Look up a musicbrainz data for a list of recordings, based on MBID.

        :param skip_not_found: If skip_not_found is set to True (the default) then Recordings that cannot be found in MusicBrainz will not be returned from this Element.
    '''

    SERVER_URL = "https://labs.api.listenbrainz.org/recording-mbid-lookup/json?count=%d"

    def __init__(self, skip_not_found=True):
        Element.__init__(self)
        self.skip_not_found = skip_not_found

    @staticmethod
    def inputs():
        return [ Recording, Playlist ]

    @staticmethod
    def outputs():
        return [ Recording, Playlist ]

    def read(self, inputs):

        if isinstance(inputs[0], Playlist):
            recordings = inputs[0].recordings
        else:
            recordings = inputs[0]
        if not recordings:
            return []

        data = []
        for r in recordings:
            data.append({ '[recording_mbid]': r.mbid })

        self.debug("- debug %d recordings" % len(recordings))

        r = requests.post(self.SERVER_URL % len(recordings), json=data)
        if r.status_code != 200:
            raise PipelineError("Cannot fetch recordings from ListenBrainz: HTTP code %d" % r.status_code)

        try:
            rows = ujson.loads(r.text)
            self.debug("- debug %d rows in response" % len(rows))
        except ValueError as err:
            raise PipelineError("Cannot fetch recordings from ListenBrainz: " + str(err))

        mbid_index = {}
        for row in rows:
            mbid_index[row['original_recording_mbid']] = row

        output = []
        for r in recordings:
            try:
                row = mbid_index[r.mbid]
                if row["recording_mbid"] is None:
                    continue
            except KeyError:
                if self.skip_not_found:
                    self.debug("- debug recording MBID %s not found, skipping." % r.mbid)
                else:
                    output.append(r)
                continue

            if not r.artist:
                a = Artist(name=row['artist_credit_name'],
                           mbids=row.get('[artist_credit_mbids]', []),
                           artist_credit_id=row['artist_credit_id'])
                r.artist = a
            else:
                r.artist.name = row['artist_credit_name']
                r.artist.mbids = row.get('[artist_credit_mbids]', [])
                r.artist.artist_credit_id = row['artist_credit_id']

            r.name = row['recording_name']
            r.length = row['length']
            r.mbid = row['recording_mbid']

            r.listenbrainz["canonical_recording_mbid"] = row["canonical_recording_mbid"]

            output.append(r)

        if isinstance(inputs[0], Playlist):
            inputs[0].recordings = output
            output = inputs[0]

        return output
