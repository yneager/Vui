# Vui

A futuristic streaming interface concept with a cinematic **homepage** and a standalone **video player UI**.

Vui is intentionally visual-first: the homepage and player are designed as a premium front-end layer you can connect to your own playback, account, search, recommendation, or C++ application logic later.

## Pages

- `index.html` — streaming homepage / discovery experience
- `home.css` — homepage visuals and motion
- `player.html` — original futuristic video player UI
- `styles.css` — player visuals and motion

## Homepage

The homepage includes:

- Floating glass navigation
- Large cinematic featured hero
- Continue-watching rail with progress treatments
- Trending poster rail with hover expansion
- Curated collection cards
- New-release landscape rail
- Animated planets, grids, light beams, glows, auroras, and microinteractions
- Responsive desktop, tablet, and mobile layouts
- Reduced-motion accessibility support
- No JavaScript dependencies

Cards and the hero currently link to `player.html` as a visual demo flow.

## Player

The player interface includes:

- Glass / depth-based control surfaces
- Animated ambient lighting
- CSS-only progress / scrubber treatment
- Animated play-state centerpiece
- Chapter / scene indicator
- Quick action rail
- 4K/HDR status badge
- Responsive layouts
- No playback JavaScript or media source

## Run it

Open `index.html` directly in a browser, or serve the folder:

```bash
python3 -m http.server 8080
```

Then open `http://localhost:8080`.

## Connecting your own app

For a real application, replace the placeholder content metadata and wire navigation/player controls to your existing logic.

For C++ desktop applications, Vui can be embedded as an HTML/CSS front end using Qt WebEngine, CEF, or WebView2, or rebuilt into QML while retaining the same visual system.
