# Reel Music — Mobile App Integration Guide

**For:** the React Native app team
**Backend status:** done and deployed
**What you build:** a song picker, a trim screen, and playback

---

## 1. What this module does

A merchant records a reel. Now they can also pick a song for it.

The flow you are building:

```
Merchant records a reel
        ↓
Taps "Add music"
        ↓
Sees a list of songs  ──────────►  GET /api/music/songs
        ↓
Taps a song, hears a preview
        ↓
Drags to pick which part of the song to use
        ↓
Taps Done  ─────────────────────►  PUT /api/reels/{id}/audio
        ↓
Song is now attached to that reel
```

That is the whole feature.

---

## 2. How it works (read this first)

Two things about the design will save you time.

### The app never uploads audio

Merchants cannot upload their own songs. Only admins add songs, from an admin
page on the website. Your app only reads the list.

This is on purpose. If merchants could upload music, they would upload songs we
do not have the rights to, and the platform gets the legal problem.

### The app sends a choice, not a file

When the merchant taps Done, you do **not** send audio, and you do **not** mix
the song into the video.

You send three numbers:

```json
{ "song_id": 42, "start_ms": 30000, "end_ms": 45000 }
```

That means "use song 42, from 30 seconds to 45 seconds". The server stores it.

Because of this, changing the song later is one API call. Nothing has to be
re-uploaded.

---

## 3. Setup

**Base URL:** same as the rest of your app (`VITE_API_BASE_URL` equivalent).

**Auth:** every endpoint below needs the merchant's normal login token.

```
Authorization: Bearer <access_token>
```

**Every response looks like this:**

```json
{ "message": "Songs retrieved", "data": { ... } }
```

On an error you get a status code of 400/403/404 and:

```json
{ "message": "Song not found or no longer available." }
```

Always show `message` to the user. The backend writes those messages for people,
not for logs.

---

## 4. API reference

### 4.1 Get the song list

```
GET /api/music/songs?category=trending&page=1&per_page=20
```

| Param | What it does | Default |
|---|---|---|
| `category` | `trending`, `new`, `popular`, `all`, or any tag like `festive` | `trending` |
| `q` | search text — matches title, artist and tags | none |
| `page` | page number, starts at 1 | 1 |
| `per_page` | how many per page, **max 50** | 20 |

**Response:**

```json
{
  "message": "Songs retrieved",
  "data": {
    "songs": [
      {
        "song_id": 42,
        "title": "Happy Vibes",
        "artist": "Music Unlimited",
        "artwork_url": "https://cdn.../cover.jpg",
        "duration_ms": 180000,
        "preview_url": "https://cdn.../track.mp3",
        "tags": ["trending", "happy"],
        "language": null,
        "usage_count": 12,
        "attribution_required": false,
        "attribution_text": null,
        "provider": "manual"
      }
    ],
    "pagination": { "page": 1, "per_page": 20, "total": 57, "pages": 3 }
  }
}
```

Use `preview_url` to play songs in the list.

There is **no `audio_url` here**, and that is deliberate. Loading a list of 50
songs should not hand out 50 full-track links.

### 4.2 Get one song (for the trim screen)

```
GET /api/music/songs/42
```

Same fields as above, plus two more:

```json
{
  "audio_url": "https://cdn.../track.mp3",
  "waveform_peaks": [0.12, 0.44, 0.91, ...]
}
```

- `audio_url` — the full track
- `waveform_peaks` — **120 numbers between 0 and 1**, ready to draw

Call this when the merchant taps a song to open the trim screen.

**Do not calculate the waveform on the phone.** The server already did it. Doing
it on device is slow on cheap Android phones, and the same song ends up looking
different on different devices.

### 4.3 Get the category tabs

```
GET /api/music/categories
```

```json
{ "data": { "categories": ["trending", "new", "popular", "happy", "festive"] } }
```

Use these as the tabs at the top of the picker. Do not hardcode them — admins add
new tags over time.

### 4.4 Attach a song to a reel

```
PUT /api/reels/{reel_id}/audio
```

```json
{
  "song_id": 42,
  "start_ms": 30000,
  "end_ms": 45000,
  "music_volume": 1.0,
  "original_volume": 0.15
}
```

| Field | Required | Notes |
|---|---|---|
| `song_id` | yes | |
| `start_ms` | no | where the clip starts. Default 0 |
| `end_ms` | no | where it ends. Must be **after** `start_ms` |
| `music_volume` | no | 0 to 1. Default 1.0 |
| `original_volume` | no | 0 to 1. Default 0.15 |

`original_volume` is the merchant's own recorded sound. It defaults to 0.15 and
not 0 on purpose, so a merchant talking about the product can still be heard
under the music.

**Errors you should handle:**

| Status | When | What to show |
|---|---|---|
| 400 | `end_ms` is not after `start_ms` | fix your trim UI, this is a bug |
| 400 | clip starts after the song ends | fix your trim UI, this is a bug |
| 404 | song was removed by an admin | "This song is no longer available" and reload the list |
| 404 | reel is not this merchant's | should not happen |

Calling this again just replaces the old choice. There is no separate "update".

### 4.5 Read what is attached

```
GET /api/reels/{reel_id}/audio
```

```json
{
  "data": {
    "reel_id": 7,
    "song_id": 42,
    "start_ms": 30000,
    "end_ms": 45000,
    "music_volume": 1.0,
    "original_volume": 0.15,
    "rendered": false,
    "song": { "song_id": 42, "title": "Happy Vibes", "..." : "..." }
  }
}
```

If nothing is attached, `data` is `null`. Not an error — just show "Add music".

### 4.6 Remove the song

```
DELETE /api/reels/{reel_id}/audio
```

### 4.7 "Use this sound"

```
GET /api/music/songs/42/reels?page=1
```

Every reel that uses this song. Good for a screen like Instagram's, where tapping
a song shows all reels using it. **No login needed** for this one.

---

## 5. Screen 1 — the song picker

What it needs:

- Tabs from `/api/music/categories`
- A search box (send as `q`)
- A scrolling list from `/api/music/songs`
- Each row: artwork, title, artist, length
- Tap a row → play `preview_url`
- Tap again → pause

**One audio player for the whole screen.** Not one per row. If each row has its
own player, four songs end up playing at once after a few taps.

```jsx
const [playingId, setPlayingId] = useState(null);

const play = async (song) => {
  if (playingId === song.song_id) { await pause(); return; }
  await stopCurrent();
  await loadAndPlay(song.preview_url);
  setPlayingId(song.song_id);
};
```

---

## 6. Screen 2 — the trim screen

This is the harder screen. It opens when a merchant picks a song.

What it shows:

- The waveform, drawn from `waveform_peaks` (120 bars)
- A window over the waveform that the merchant drags
- The song playing in a loop, only the selected part
- The reel video playing above, muted

### Draw the waveform

```jsx
// 120 numbers, each 0..1
<View style={{ flexDirection: 'row', alignItems: 'center', height: 60 }}>
  {peaks.map((p, i) => (
    <View
      key={i}
      style={{
        flex: 1,
        marginHorizontal: 0.5,
        height: Math.max(2, p * 60),
        backgroundColor: isInsideWindow(i) ? '#1800AC' : '#D1D5DB',
      }}
    />
  ))}
</View>
```

### Make the window a fixed size

The clip should be **as long as the reel**. So the merchant drags the window left
and right, but does not resize it.

```
reel is 15 seconds  →  window is always 15 seconds wide
merchant drags      →  only start_ms changes
end_ms = start_ms + reel_duration
```

This is how Instagram does it, and it is much easier to use on a phone than two
separate handles.

### Convert drag position to milliseconds

```js
const songMs   = song.duration_ms;      // e.g. 180000
const clipMs   = reelDurationMs;        // e.g. 15000
const maxStart = Math.max(0, songMs - clipMs);

// dragRatio is 0..1, how far along the waveform the window sits
const startMs = Math.round(dragRatio * maxStart);
const endMs   = startMs + clipMs;
```

### Preview it properly

While the merchant is on this screen, play what they will actually get:

- Video: muted, looping
- Audio: `audio_url`, seek to `start_ms`, loop back to `start_ms` at `end_ms`

If they cannot hear the result before saving, they will save the wrong part.

---

## 7. Saving

On Done:

```js
await fetch(`${BASE_URL}/api/reels/${reelId}/audio`, {
  method: 'PUT',
  headers: {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ song_id: song.song_id, start_ms, end_ms }),
});
```

That is it. No file upload, no waiting for processing.

---

## 8. Playing reels in the feed

The reel video and the song are separate. You have two options.

### Option A — the server mixes it (simpler for you)

If `rendered` is `true` in the reel audio response, the video file already has
the music in it. Just play the video normally. Nothing special to do.

### Option B — the app mixes at playback

If `rendered` is `false`, you play the video muted and the song alongside it.

**Do not use two separate players.** They drift apart and you will spend weeks
chasing it. Use the built-in tools:

- **Android:** ExoPlayer `MergingMediaSource`
- **iOS:** `AVMutableComposition`

Both keep video and audio on one timeline, so the player handles sync itself.

Ask the backend team which option is live before you build this part.

---

## 9. Libraries

| Need | Suggested |
|---|---|
| Play audio | `react-native-track-player` |
| Play video | `react-native-video` |
| Waveform | plain `<View>` bars — no library needed |
| Drag gesture | `react-native-gesture-handler` |

You do not need a waveform library. The server sends 120 numbers and you draw 120
rectangles.

---

## 10. Mistakes to avoid

**Do not calculate the waveform on the phone.** The server sends it. Slow on
cheap phones, and looks different on each device.

**Do not send audio files.** There is no endpoint for it. Send `song_id` and
`start_ms`.

**Do not use `audio_url` in the list screen.** It is not there. Use
`preview_url`. Only fetch the full track for the one song the merchant picked.

**Do not hardcode the category tabs.** Fetch them. Admins add tags over time.

**Do not use one audio player per list row.** One player for the whole screen.

**Do not assume `original_volume` is 0.** The merchant's own sound stays at 0.15
by default so their voice is still audible under the music.

**Do not treat "no audio attached" as an error.** `data: null` from
`GET /api/reels/{id}/audio` just means no song was picked yet.

---

## 11. Quick test

Before building the UI, check the API works:

```bash
TOKEN="<merchant access token>"
BASE="https://api.aoinstore.com"

# see the songs
curl -s "$BASE/api/music/songs?category=trending" \
     -H "Authorization: Bearer $TOKEN" | head -40

# attach one to reel 1
curl -s -X PUT "$BASE/api/reels/1/audio" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"song_id": 1, "start_ms": 0, "end_ms": 15000}'

# read it back
curl -s "$BASE/api/reels/1/audio" -H "Authorization: Bearer $TOKEN"
```

If the song list comes back empty, ask the admin team to add songs in
**Superadmin → Music Library** first.

---

## 12. Who to ask

- **Song list is empty** → admin team, they add songs
- **A song disappeared** → an admin removed it; handle the 404 and reload
- **Sync problems in the feed** → backend team, ask whether Option A or B is live
