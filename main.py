from mutagen.easyid3 import EasyID3
from dateutil.parser import parse
from mutagen.mp3 import MP3
from time import sleep
from tqdm import tqdm
import discogs_client
import argparse
import mutagen
import difflib
import fnmatch
import pickle
import sys
import os

parser = argparse.ArgumentParser(description='Slice mp3 recording into tracks, edit ID3 via discogs collection lookup, and add to iTunes.')
parser.add_argument('--artist', type=str, help='Artist Name')
parser.add_argument('--title', type=str, help='Release Title')
parser.add_argument('--filename', type=str, help='Recording File Name', required=True)
args = parser.parse_args()

# TODO: Create classes for these objects
class Recording:
  pass

class Collection:
  pass

class CollectionList:
  pass

def splitRecording(filename):
  os.system("mp3splt -s -p th=-30,min=3,rm {}.mp3".format(filename))

def getRecordingContext(filename):
  recordingContext = []
  for file in os.listdir('.'):
    if fnmatch.fnmatch(file, '{}_silence_*.mp3'.format(filename)):
      audio = MP3(file)
      m = int(audio.info.length / 60)
      s = int(audio.info.length % 60)
      recordingContext.append(int(audio.info.length))
  return recordingContext

def editMetadata(filename, winningCandidate):
  filesToEdit = []
  for file in os.listdir('.'):
    if fnmatch.fnmatch(file, '{}_silence_*.mp3'.format(filename)):
      filesToEdit.append(file)
  for i, f in enumerate(filesToEdit):
    try:
       meta = EasyID3(f)
    except mutagen.id3.ID3NoHeaderError:
       meta = mutagen.File(f, easy=True)
       meta.add_tags()
    meta["artist"] = winningCandidate[1]
    meta["album"] = winningCandidate[2]
    meta["date"] = str(winningCandidate[3])
    meta["genre"] = winningCandidate[4]
    meta["title"] = winningCandidate[5][i]
    meta["tracknumber"] = str(i)
    meta.save()
    dst = "{} - {}.mp3".format(winningCandidate[1], winningCandidate[5][i])
    os.rename(f, dst)

def getDiscogsCollection():
  # TODO: gather values from local env.
  d = discogs_client.Client("CLIENTIDSTRING", user_token="USERTOKEN")
  joey = d.identity()
  return joey.collection_folders[0].releases.sort("added", "desc")

def collectionToCollectionList(collection):
  print("downloading collection...")
  collectionlist = []
  for album in tqdm(collection):
    sleep(1)
    collectionlist.append([
      album.data['date_added'],
      album.release.artists[0].name,
      album.release.title,
      album.release.year,
      album.release.genres[0],
      [t.title for t in album.release.tracklist],
      [t.duration for t in album.release.tracklist],
    ])
  return collectionlist

def pickleCollection(collectionlist):
  output = open('collectionlist.pkl', 'wb')
  print("pickling collection...")
  pickle.dump(collectionlist, output)

def unpickleCollection(filename='collectionlist.pkl'):
  pkl_file = open(filename, 'rb')
  return pickle.load(pkl_file)

def discogsCollectionChanged(collection):
  c = unpickleCollection()
  latestDateFromPickle = parse(c[0][0])
  latestDateFromDiscogs = parse(collection[0].data['date_added'])
  if latestDateFromDiscogs != latestDateFromPickle:
    return True
  else:
    return False

def getReleaseCandidates(collectionlist, recordingContext):
  candidates = []
  for album in collectionlist:
    releaseContext = []
    for duration in album[6]:
      if len(duration) > 0:
        m, s = duration.split(":")
        duration = int(m) * 60 + int(s)
        releaseContext.append(duration)
    # if recording context is similar to collection release context, add it to candidates list
    # first, at a minimum we need the same number of tracks
    if len(releaseContext) == len(recordingContext):
      distances = []
      for i, dur in enumerate(releaseContext):
        distances.append(abs(dur - recordingContext[i]))
      totalDistance = sum(distances)
      # if they have a high ratio of numeric similarity (fuzzy like-ness), pass them
      if totalDistance < (7 * len(releaseContext)):
        candidates.append(album)
  return candidates

if __name__ == "__main__":
  splitRecording(args.filename)
  RC = getRecordingContext(args.filename)
  collection = getDiscogsCollection()
  if not os.path.isfile("collectionlist.pkl"):
    pickleCollection(collection)
  if discogsCollectionChanged(collection):
    saveNewCollectionAdditions()
  collectionlist = unpickleCollection()
  candidates = getReleaseCandidates(collectionlist, RC)
  if len(candidates) == 1:
    print candidates[0]
    # edit Id3 tags
    editMetadata(args.filename, candidates[0])
    # add to iTunes
    
    # initiate upload