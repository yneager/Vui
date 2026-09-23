# Vui

A futuristic, animation-heavy **video player UI concept** with **zero playback functionality**.

The goal is to give you a premium visual layer you can graft onto an existing video player without bringing in another playback stack.

## What is included

- Glass / depth-based control surfaces
- Animated ambient lighting and background motion
- CSS-only progress / scrubber treatment
- Animated play-state centerpiece
- Chapter / scene indicator
- Compact left-side quick action rail
- Futuristic 4K/HDR status badge
- Responsive desktop, tablet, and mobile layouts
- Reduced-motion accessibility support
- No JavaScript and no playback logic
- Inline SVG icons and no icon library dependency

## Run it

Open `index.html` directly in a browser, or serve the folder with any static server.

Example:

```bash
python3 -m http.server 8080
```

Then open `http://localhost:8080`.

## Integrating into an existing player

The visual layer is split into clear regions:

- `.topbar` — media title + global actions
- `.side-rail` — quick action rail
- `.center-state` — idle / paused centerpiece
- `.quality-badge` — quality status
- `.control-deck` — timeline and main controls

Replace the `.poster` element with your actual video element or place this UI above your existing video using `position: absolute` inside the same player container.

The interface intentionally contains no event handlers, playback state, media source, or JavaScript.

## Design tokens

The main theme variables live at the top of `styles.css`:

```css
:root {
  --cyan: #78f5e7;
  --violet: #a788ff;
  --panel: rgba(15, 18, 26, 0.58);
  --text: #f7f8fb;
}
```

Swap those values to retheme the whole interface quickly.