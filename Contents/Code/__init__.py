# LiveTVH - Live TV streaming for Plex via Tvheadend
# https://github.com/taligentx/LiveTVH


# Display the EPG zap2it ID for a show in the channel summary if the ID on theTVDB.com does not match
# due to a missing ID, outdated ID, or incorrect show match.  If the show matches correctly, consider
# contributing by updating the entry on thetvdb.com to improve search results.
improveTheTVDB = True

# Cache times
epgCacheTime = CACHE_1DAY
imageCacheTime = CACHE_1MONTH
tvdbRetryInterval = CACHE_1MONTH


liveTVHVersion = '1.0'
TITLE = 'LiveTVH'
PREFIX = '/video/livetvh'
THUMB = 'LiveTVH-thumb.jpg'
ART = 'LiveTVH-art.jpg'


import base64, time
tvhHeaders = None
tvhAddress = None
tvhReachable = False
tvdbToken = None
tmdbBaseURL = None
tmdbGenreData = None


def Start():
    setPrefs()
    Log.Info("LiveTVH version: " + liveTVHVersion)


@route(PREFIX + '/validateprefs')
def ValidatePrefs():
    setPrefs()
    return True


# Setup authorization and configuration data
@route(PREFIX + '/setprefs')
def setPrefs():
    global tvhHeaders
    global tvhAddress
    global tvhReachable
    global tvdbToken
    global tmdbBaseURL
    global tmdbGenreData

    # Set Tvheadend authorization and verify connectivity to Tvheadend
    tvhAuth = base64.b64encode('%s:%s' % (Prefs['tvhUser'], Prefs['tvhPass']))
    tvhHeaders = {'Authorization': 'Basic %s' % tvhAuth}
    tvhAddress = Prefs['tvhAddress'].rstrip('/')
    tvhServerInfoURL = '%s/api/serverinfo' % tvhAddress

    try:
        tvhInfoData = JSON.ObjectFromURL(url=tvhServerInfoURL, headers=tvhHeaders, values=None, cacheTime=1)
        if tvhInfoData['api_version'] >= 15:
            tvhReachable = True
        else:
            Log.Critical("Tvheadend version " + tvhInfoData['sw_version'] + " is unsupported.")
            return
    except Exception as e:
        Log.Critical("Error accessing Tvheadend: " + str(e))
        tvhReachable = False
        return

    # Renew theTVDB authorization token if necessary
    if Prefs['prefMetadata'] == True and tvdbToken != None:
        tvdbToken = None
        tvdbAuth()

    # Retrieve themovieDB base URL for images and genre list
    if Prefs['prefMetadata'] == True:
        tmdbConfigURL = 'https://api.themoviedb.org/3/configuration?api_key=0fd2136e80c47d0e371ee1af87eaedde'
        tmdbGenreURL = 'https://api.themoviedb.org/3/genre/movie/list?api_key=0fd2136e80c47d0e371ee1af87eaedde'

        try:
            tmdbConfigData = JSON.ObjectFromURL(url=tmdbConfigURL, values=None, cacheTime=1)
            tmdbGenreData = JSON.ObjectFromURL(url=tmdbGenreURL, values=None, cacheTime=1)
            tmdbBaseURL = tmdbConfigData['images']['base_url']
        except Exception as e:
            Log.Warn("Error accessing themovieDB: " + str(e))


# Build the channel list
@handler(PREFIX, TITLE, art=ART, thumb=THUMB)
def MainMenu():
    mainMenuContainer = ObjectContainer(title1=TITLE, no_cache=True)

    # Get channel and EPG data from Tvheadend
    tvhChannelsData = None
    tvhEPGData = None
    tvhChannelURL = '%s/api/channel/grid?start=0&limit=1000' % tvhAddress
    tvhEPGURL = '%s/api/epg/events/grid?start=0&limit=10000' % tvhAddress

    if tvhReachable == True:

        try: tvhChannelsData = JSON.ObjectFromURL(url=tvhChannelURL, headers=tvhHeaders, values=None, cacheTime=epgCacheTime)
        except Exception as e: Log.Critical("Error retrieving Tvheadend channel data: " + str(e))

        try: tvhEPGData = JSON.ObjectFromURL(encoding='utf-8', url=tvhEPGURL, headers=tvhHeaders, values=None, cacheTime=epgCacheTime)
        except:
            try:
                # Tvheadend's ATSC OTA EPG grabber sends UTF-8 characters as ISO-8859-1
                rawEPGData = HTTP.Request(url=tvhEPGURL, headers=tvhHeaders, cacheTime=epgCacheTime, values=None, encoding='latin-1').content
                tvhEPGData = JSON.ObjectFromString(rawEPGData, encoding='utf-8')
            except Exception as e: Log.Warn("Error retrieving Tvheadend EPG data: " + str(e))

    # Set metadata for each channel and add to the main menu
    if tvhChannelsData != None: 
        for tvhChannel in sorted(tvhChannelsData['entries'], key=lambda t: float(t['number'])):

            # Set channel metadata using Tvheadend channel info
            try: title = tvhChannel['name']
            except: title = None
            if (Prefs['prefChannelNumbers'] == True):
                if title: title = str(tvhChannel['number']) + " " + title
                else: title = str(tvhChannel['number'])
            uuid = tvhChannel['uuid']
            thumb = None
            fallbackThumb = None
            art = R(ART)
            summary = None
            tagline = None
            source_title = None
            year = None
            rating = 0.0
            content_rating = None
            genres = ' '

            # Set channel metadata using Tvheadend EPG info
            if tvhEPGData != None:
                for tvhEPGEntry in tvhEPGData['entries']:
                    if tvhEPGEntry['channelUuid'] == uuid and time.time() >= int(tvhEPGEntry['start']) and time.time() < int(tvhEPGEntry['stop']):
                        if tvhEPGEntry.get('title'):

                            # Set the show title
                            title = title + ": " + tvhEPGEntry['title']

                            # Set times
                            if (Prefs['pref24Time'] == True):
                                startTime = time.strftime("%H:%M", time.localtime(int(tvhEPGEntry['start'])))
                                stopTime = time.strftime("%H:%M", time.localtime(int(tvhEPGEntry['stop'])))
                            else:
                                startTime = time.strftime("%I:%M%P", time.localtime(int(tvhEPGEntry['start']))).lstrip('0')
                                stopTime = time.strftime("%I:%M%P", time.localtime(int(tvhEPGEntry['stop']))).lstrip('0')

                            # Set the episode title and summary
                            if Client.Product == 'Plex Web':
                                title = title + "                              " # Force Plex Web to use the Details view by padding the title
                                tagline = startTime + '-' + stopTime
                                if tvhEPGEntry.get('subtitle'):
                                    tagline = tagline + ': ' + tvhEPGEntry['subtitle']
                                if tvhEPGEntry.get('description'):
                                    summary = tvhEPGEntry['description'] + '\n'

                            elif Client.Product == 'Plex for Roku':
                                source_title = startTime + '-' + stopTime
                                if tvhEPGEntry.get('subtitle'):
                                    source_title = source_title + ': ' + tvhEPGEntry['subtitle']
                                if tvhEPGEntry.get('description'):
                                    summary = tvhEPGEntry['description'] + '\n'

                            elif Client.Product == 'Plex for Android':
                                source_title = startTime + '-' + stopTime
                                summary = startTime + '-' + stopTime
                                if tvhEPGEntry.get('description'):
                                    summary = summary + ': ' + tvhEPGEntry['description'] + '\n'
                                else:
                                    summary = summary + '\n'

                            else:
                                if tvhEPGEntry.get('subtitle'):
                                    title = title + " (" + tvhEPGEntry['subtitle'] + ")"
                                summary = startTime + '-' + stopTime
                                if tvhEPGEntry.get('description'):
                                    summary = summary + ': ' + tvhEPGEntry['description'] + '\n'
                                else:
                                    summary = summary + '\n'

                            # List upcoming titles on this channel in the summary by searching for shows
                            # in the next number of hours or number of entries, whichever is greater
                            if tvhEPGEntry.get('nextEventId'):
                                nextEventID = tvhEPGEntry['nextEventId']
                                epgLimit = int(Prefs['prefEPGCount'])
                                timeLimit = int(time.time()) + (int(Prefs['prefEPGCount'])*3600)
                                nextEPGCount = 1
                                nextEPGLoop = True
                                while nextEPGLoop == True:
                                    for nextEntry in tvhEPGData['entries']:
                                        nextEntryStart = int(nextEntry['start'])
                                        try:
                                            if nextEntry['eventId'] == nextEventID and (nextEntryStart <= timeLimit or nextEPGCount <= epgLimit):
                                                if (Prefs['pref24Time'] == True):
                                                    nextStart = time.strftime("%H:%M", time.localtime(nextEntryStart))
                                                else:
                                                    nextStart = time.strftime("%I:%M%P", time.localtime(nextEntryStart)).lstrip('0')
                                                if summary: summary = summary + nextStart + ": " + nextEntry['title'] + '\n'
                                                else: summary = nextStart + ": " + nextEntry['title'] + '\n'
                                                nextEventID = nextEntry['nextEventId']
                                                nextEPGCount += 1
                                                if nextEPGCount > epgLimit and nextEntryStart > timeLimit:
                                                    break
                                            else:
                                                nextEPGLoop = False
                                        except KeyError: pass

                            # Check if this title has a zap2it ID
                            zap2itID = None
                            try:
                                if tvhEPGEntry.get('episodeUri'):
                                    epgID=tvhEPGEntry['episodeUri'].split("/")[3].split(".")[0]
                                    if epgID.startswith('MV') or epgID.startswith('EP') or epgID.startswith('SH'):
                                        zap2itID = epgID
                            except: pass

                            # Find metadata for this title
                            if Prefs['prefMetadata'] == True:
                                metadataResults = metadata(title=tvhEPGEntry['title'], zap2itID=zap2itID)
                                if metadataResults['thumb'] != None: thumb = metadataResults['thumb']
                                if metadataResults['art'] != None: art = metadataResults['art']
                                if metadataResults['year'] != None: year = metadataResults['year']
                                if metadataResults['rating'] != None: rating = metadataResults['rating']
                                if metadataResults['content_rating'] != None: content_rating = metadataResults['content_rating']
                                if metadataResults['genres'] != None: genres = metadataResults['genres']
                                if metadataResults['zap2itMissingID'] != None and improveTheTVDB == True: summary = metadataResults['zap2itMissingID'] + " | " + summary

            # Use channel icons from Tvheadend as a fallback to remote artwork
            try:
                if thumb == None and tvhChannel['icon_public_url'].startswith('imagecache'):
                    thumb = '%s/%s' % (tvhAddress, tvhChannel['icon_public_url'])
                if tvhChannel['icon_public_url'].startswith('imagecache'):
                    fallbackThumb ='%s/%s' % (tvhAddress, tvhChannel['icon_public_url'])
            except: pass

            # Build and add the channel to the main menu as either a MovieObject or VideoClipObject based on the client
            # Plex for Roku only displays source_title for VideoClipObjects
            if Client.Product == 'Plex for Roku':
                mainMenuContainer.add(channelVideoClipObject(title=title, uuid=uuid, thumb=thumb, fallbackThumb=fallbackThumb, art=art, summary=summary, tagline=tagline, source_title=source_title, year=year, rating=rating, content_rating=content_rating, genres=genres))
            else:
                mainMenuContainer.add(channel(title=title, uuid=uuid, thumb=thumb, fallbackThumb=fallbackThumb, art=art, summary=summary, tagline=tagline, source_title=source_title, year=year, rating=rating, content_rating=content_rating, genres=genres))

    # Display an error message to clients if Tvheadend is malfunctional
    else:
        mainMenuContainer.add(DirectoryObject(title=L("channelsUnavailable")))

    # Add the built-in Preferences object to the main menu - visible on OpenPHT
    mainMenuContainer.add(PrefsObject(title=L('preferences')))
    return mainMenuContainer


# Build the channel as a MovieObject
@route(PREFIX + '/channel')
def channel(title, uuid, thumb, fallbackThumb, art, summary, tagline, source_title, year, rating, content_rating, genres, container=False, checkFiles=0, **kwargs):
    channelObject = MovieObject(
        key = Callback(channel, title=title, uuid=uuid, thumb=thumb, fallbackThumb=fallbackThumb, art=art, summary=summary, tagline=tagline, source_title=source_title, year=year, rating=rating, content_rating=content_rating, genres=genres, container=True, checkFiles=0, **kwargs),
        rating_key = uuid,
        title = title,
        thumb = Callback(image, url=thumb, fallback=fallbackThumb),
        art = Callback(image, url=art, fallback=R(ART)),
        summary = summary,
        source_title = source_title,
        tagline = tagline,
        year = year,
        rating = float(rating),
        content_rating = content_rating,
        duration = 86400000,
        genres = [genres],
        items = [
            MediaObject(
                parts = [
                    PartObject(
                        key=Callback(stream, uuid=uuid),
                        streams=[
                            VideoStreamObject(codec='mpeg2video'),
                            AudioStreamObject(codec='ac3')
                        ]
                    )
                ],
                container = 'mpegts',
                optimized_for_streaming = False
            )
        ]
    )
    if container:
        return ObjectContainer(objects=[channelObject])
    else:
        return channelObject


# Build the channel as a VideoClipObject for clients that do not work as well with MovieObject
@route(PREFIX + '/channelvco')
def channelVideoClipObject(title, uuid, thumb, fallbackThumb, art, summary, tagline, source_title, year, rating, content_rating, genres, container=False, checkFiles=0, **kwargs):
    channelObject = VideoClipObject(
        key = Callback(channelVideoClipObject, title=title, uuid=uuid, thumb=thumb, fallbackThumb=fallbackThumb, art=art, summary=summary, tagline=tagline, source_title=source_title, year=year, rating=rating, content_rating=content_rating, genres=genres, container=True, checkFiles=0, **kwargs),
        rating_key = uuid,
        title = title,
        thumb = Callback(image, url=thumb, fallback=fallbackThumb),
        art = Callback(image, url=art, fallback=R(ART)),
        summary = summary,
        source_title = source_title,
        tagline = tagline,
        year = year,
        rating = float(rating),
        content_rating = content_rating,
        duration = 86400000,
        genres = [genres],
        items = [
            MediaObject(
                parts = [
                    PartObject(
                        key=Callback(stream, uuid=uuid),
                        streams=[
                            VideoStreamObject(codec='mpeg2video'),
                            AudioStreamObject(codec='ac3')
                        ]
                    )
                ],
                container = 'mpegts',
                optimized_for_streaming = True
            )
        ]
    )
    if container:
        return ObjectContainer(objects=[channelObject])
    else:
        return channelObject


# Search for images with fallback
# theTVDB API requires a separate HTTP request for each piece of artwork, so the
# channel list load time can be reduced by running the search asynchronously
@route(PREFIX + '/image')
def image(url=None, fallback=None):
    if url == None and fallback == None: return None

    if 'api.thetvdb.com' in url:
        tvdbHeaders = {'Authorization' : 'Bearer %s' % tvdbToken}
        tvdbImageData = None

        try:
            tvdbImageData = JSON.ObjectFromURL(url=url, headers=tvdbHeaders, values=None, cacheTime=imageCacheTime)
        except Ex.HTTPError as e:
            if e.code == 404:
                if fallback == R(ART):
                    return Redirect(R(ART))
                elif fallback != None:
                    imageContent = HTTP.Request(url=fallback, cacheTime=imageCacheTime, values=None).content
                    return DataObject(imageContent, 'image/jpeg')
                else: return None

        if tvdbImageData != None:
            for tvdbImageResult in tvdbImageData['data']:
                url = 'http://thetvdb.com/banners/' + tvdbImageResult['fileName']
                imageContent = HTTP.Request(url, cacheTime=imageCacheTime, values=None).content
                return DataObject(imageContent, 'image/jpeg')

    elif tvhAddress in url:
        try:
            imageContent = HTTP.Request(url=url, headers=tvhHeaders, cacheTime=imageCacheTime, values=None).content
            return DataObject(imageContent, 'image/jpeg')
        except:
            return None

    elif url == R(ART):
        return Redirect(R(ART))

    else:
        imageContent = HTTP.Request(url, cacheTime=imageCacheTime, values=None).content
        return DataObject(imageContent, 'image/jpeg')


# Build the Tvheadend stream URL and verify availability
@route(PREFIX + '/stream')
@indirect
def stream(uuid):

    # Add basic authentication info to the channel URL - Plex ignores the headers parameter in PartObject
    tvhBasicAuth = '//%s:%s@' % (Prefs['tvhUser'], Prefs['tvhPass'])
    tvhAuthAddress = tvhAddress.replace('//',tvhBasicAuth)
    streamURL = '%s/stream/channel/%s' % (tvhAuthAddress, uuid)

    if Prefs['tvhProfile'] != None:
        streamURL = streamURL + '?profile=' + Prefs['tvhProfile']

    # Verify the channel is available before returning it to PartObject
    testURL = '%s/stream/channel/%s' % (tvhAddress, uuid)

    try:
        responseCode = HTTP.Request(testURL, headers=tvhHeaders, values=None, cacheTime=None, timeout=1).headers
        return IndirectResponse(MovieObject, key=streamURL)
    except Exception as e:
        Log.Warn("Tvheadend is not responding to this channel request - verify that there are available tuners: " + repr(e))
        raise Ex.MediaNotAvailable


# Search for metadata
@route(PREFIX + '/metadata')
def metadata(title, zap2itID):
    thumb = None
    art = None
    year = None
    rating = None
    content_rating = None
    genres = None
    zap2itMissingID = None

    # Skip searching theTVDB if EPG data states the title is a movie
    if str(zap2itID).startswith('MV') == True: epgMovie = True
    else: epgMovie = False

    # Search theTVDB
    if (thumb == None or art == None) and epgMovie == False:
        tvdbResults = tvdb(title, zap2itID)
        if tvdbResults != None:
            if thumb == None: thumb = tvdbResults['poster']
            if art == None: art = tvdbResults['fanart']
            if rating == None: rating = tvdbResults['siteRating']
            if content_rating == None: content_rating = tvdbResults['rating']
            if genres == None: genres = tvdbResults['genres']
            zap2itMissingID = tvdbResults['zap2itMissingID']

    # Search themovieDB
    if thumb == None or art == None:
        tmdbResults = tmdb(title, epgMovie)
        if tmdbResults != None:
            if thumb == None: thumb = tmdbResults['poster']
            if art == None: art = tmdbResults['backdrop']
            if rating == None: rating = tmdbResults['vote_average']
            if year == None: year = tmdbResults['year']
            if genres == None: genres = tmdbResults['genres']

    return { 'thumb': thumb, 'art': art, 'year': year, 'rating': rating, 'content_rating': content_rating, 'genres': genres, 'zap2itMissingID': zap2itMissingID }


# Retrieve an authorization token from theTVDB
@route(PREFIX + '/tvdbauth')
def tvdbAuth():
    global tvdbToken

    tvdbLoginURL = 'https://api.thetvdb.com/login'
    tvdbApiKeyJSON = '{"apikey" : "C7DE76F57D6BE6CE"}'
    tvdbHeaders = {'content-type' : 'application/json'}

    try:
        tvdbResponse = HTTP.Request(url=tvdbLoginURL, headers=tvdbHeaders, data=tvdbApiKeyJSON, cacheTime=1).content
        tvdbTokenData = JSON.ObjectFromString(tvdbResponse)
        tvdbToken = tvdbTokenData['token']
    except Ex.HTTPError as e:
        Log.Warn("Failed to retrieve theTVDB authorization token: " + str(e))
        tvdbToken = False


# Search theTVDB for metadata
@route(PREFIX + '/tvdb')
def tvdb(title, zap2itID, zap2itMissingID=None):
    tvdbPosterSearchURL = None
    tvdbFanartSearchURL = None
    tvdbRating = None
    tvdbSiteRating = 0.0
    tvdbGenres = None
    tvdbID = None

    # Skip searching for this title if the theTVDB had no results within the configured tvdbRetryInterval.
    # This uses the framework Dict as a cache because Plex does not cache the HTTP 404 response from theTVDB API. 
    if title in Dict:
        if time.time() >= Dict[title]: pass
        else:
            h, m = divmod(int(Dict[title] - time.time()), 3600)
            d, h = divmod(h, 24)
            Log.Info("theTVDB previously had no results for " + title + ", will try again after %sd, %sh." % (d,h))
            return None

    # Request an authorization token if it doesn't exist
    if tvdbToken == None:
        Log.Info("Requesting an authorization token for theTVDB")
        tvdbAuth()
        return tvdb(title, zap2itID)
    if tvdbToken == False:
        Log.Info("theTVDB authorization failed.")
        return {'poster': tvdbPoster, 'fanart': tvdbFanart}

    # Search using zap2it ID if available, otherwise search by name
    tvdbHeaders = {'Authorization' : 'Bearer %s' % tvdbToken}

    if zap2itID != None: tvdbSearchURL = 'https://api.thetvdb.com/search/series?zap2itId=%s' % String.Quote(zap2itID)
    else: tvdbSearchURL = 'https://api.thetvdb.com/search/series?name=%s' % String.Quote(title)

    try:
        tvdbData = JSON.ObjectFromURL(url=tvdbSearchURL, headers=tvdbHeaders, values=None, cacheTime=imageCacheTime)

        for tvdbResult in tvdbData['data']:
            if zap2itID != None:
                tvdbID = tvdbResult['id']
                break
            elif String.LevenshteinDistance(tvdbResult['seriesName'], title) == 0:
                tvdbID = tvdbResult['id']
                if zap2itMissingID != None: 
                    Log.Info("Found " + title + " at http://thetvdb.com/?tab=series&id=" + str(tvdbID) + " by name but not by zap2it ID " + zap2itMissingID + " - if this match is correct, consider adding the zap2it ID to theTVDB.com to improve search results.")
                break

    except Ex.HTTPError as e:
        if e.code == 401:
            Log.Info("theTVDB authorization token is invalid, requesting a new one")
            tvdbAuth()
            return tvdb(title, zap2itID)

        if e.code == 404:
            # Search again by name if there are no results by zap2it ID, and save the ID to report
            # a possible missing/mismatched ID on thetvdb.com if there is a match by name
            if zap2itID != None:
                zap2itMissingID = zap2itID
                zap2itID = None
                return tvdb(title, zap2itID, zap2itMissingID)
            else:
                Dict[title] = time.time() + tvdbRetryInterval
                h, m = divmod(int(tvdbRetryInterval), 3600)
                d, h = divmod(h, 24)
                Log.Info("No results from theTVDB for " + title + ", skipping lookup for %s days." % d)
                return None

        else:
            Log.Warn("Error while searching theTVDB: " + str(e))
            return None

    if tvdbID != None:
        tvdbPosterSearchURL = 'https://api.thetvdb.com/series/%s/images/query?keyType=poster' % tvdbID
        tvdbFanartSearchURL = 'https://api.thetvdb.com/series/%s/images/query?keyType=fanart' % tvdbID

        # Search for metadata
        tvdbMetadataSearchURL = 'https://api.thetvdb.com/series/%s' % tvdbID
        tvdbMetadata = None

        try:
            tvdbMetadata = JSON.ObjectFromURL(url=tvdbMetadataSearchURL, headers=tvdbHeaders, values=None, cacheTime=imageCacheTime)
        except Ex.HTTPError as e:
            if e.code == 404:
                Log.Info("No metadata from theTVDB for " + title)

        if tvdbMetadata != None:
            if tvdbMetadata['data']['rating'] != '':
                tvdbRating = tvdbMetadata['data']['rating']
            if tvdbMetadata['data']['siteRating'] != '':
                tvdbSiteRating = tvdbMetadata['data']['siteRating']
            if tvdbMetadata['data']['genre'] != []:

                # Convert genres to a string - Plex will not accept a list directly for genre in the channel object
                tvdbGenres = str(tvdbMetadata['data']['genre']).lstrip('[').rstrip(']').replace("'", "")

    else:
        Dict[title] = time.time() + tvdbRetryInterval
        h, m = divmod(int(tvdbRetryInterval), 3600)
        d, h = divmod(h, 24)
        Log.Info("No results from theTVDB for " + title + ", skipping lookup for %s days." % d)
        return None

    return {'poster': tvdbPosterSearchURL, 'fanart': tvdbFanartSearchURL, 'rating': tvdbRating, 'siteRating': tvdbSiteRating, 'genres': tvdbGenres, 'zap2itMissingID': zap2itMissingID}


# Search The Movie Database for metadata
@route(PREFIX + '/tmdb')
def tmdb(title, epgMovie):
    tmdbData = None
    tmdbPoster = None
    tmdbBackdrop = None
    tmdbYear = None
    tmdbVoteAverage = 0.0
    tmdbSearchURL = 'https://api.themoviedb.org/3/search/multi?api_key=0fd2136e80c47d0e371ee1af87eaedde&query=%s' % String.Quote(title)
    tmdbGenres = None

    # Search
    try:
        tmdbData = JSON.ObjectFromURL(url=tmdbSearchURL, cacheTime=imageCacheTime, values=None)
    except Exception as e:
        Log.Warn("Error retrieving TMDb data:  " + str(e))

    # Check for a matching TV show (TMDb returns 'name') or movie (TMDb returns 'title')
    if tmdbData != None and int(tmdbData['total_results']) > 0 :
        for tmdbResult in tmdbData['results']:
            try:
                if String.LevenshteinDistance(tmdbResult['name'], title) == 0 and (tmdbResult['poster_path'] != None or tmdbResult['backdrop_path'] != None):
                    if tmdbResult['poster_path'] != None:
                        tmdbPoster = tmdbBaseURL + 'w342' + tmdbResult['poster_path']
                    if tmdbResult['backdrop_path'] != None:
                        tmdbBackdrop = tmdbBaseURL + 'original' + tmdbResult['backdrop_path']
                    if tmdbResult.get('vote_average'):
                            tmdbVoteAverage = float(tmdbResult['vote_average'])
                    if tmdbResult.get('genre_ids'):
                        for genreResultID in tmdbResult['genre_ids']:
                            for genreList in tmdbGenreData['genres']:
                                if genreResultID == genreList['id']:
                                    if tmdbGenres == None: tmdbGenres = genreList['name']
                                    else: tmdbGenres = tmdbGenres + ", " + genreList['name']
                    break
            except KeyError:
                try:
                    if String.LevenshteinDistance(tmdbResult['title'], title) == 0 and (tmdbResult['poster_path'] != None or tmdbResult['backdrop_path'] != None):
                        if tmdbResult['poster_path'] != None:
                            tmdbPoster = tmdbBaseURL + 'w342' + tmdbResult['poster_path']
                        if tmdbResult['backdrop_path'] != None:
                            tmdbBackdrop = tmdbBaseURL + 'original' + tmdbResult['backdrop_path']
                        if tmdbResult.get('release_date'):
                            year = int(tmdbResult['release_date'].split("-")[0])
                        if tmdbResult.get('vote_average'):
                            tmdbVoteAverage = tmdbResult['vote_average']
                        if tmdbResult.get('genre_ids'):
                            for genreResultID in tmdbResult['genre_ids']:
                                for genreList in tmdbGenreData['genres']:
                                    if genreResultID == genreList['id']:
                                        if tmdbGenres == None: tmdbGenres = genreList['name']
                                        else: tmdbGenres = tmdbGenres + ", " + genreList['name']
                        break
                except: pass
            except: pass
    else:
        Log.Info("No results from TMDb for " + title)

    return { 'poster': tmdbPoster, 'backdrop': tmdbBackdrop, 'year': tmdbYear, 'vote_average': tmdbVoteAverage, 'genres': tmdbGenres}