# Glean Commons 3D explainer

Two animated people walk through an invoice follow-up. The film shows how the
router finds a reusable cell, how contributors can combine tools, and how the
ledger preserves credit. It identifies Proof of Use as a proposed scorecard
with simulated rewards.

## Render

Install Python 3.10+, Blender (tested with 5.2), and FFmpeg with libx264. From
the repository root, choose a new output path in an existing folder.

```sh
python3 cells/glean-3d-explainer/render.py glean-commons-3d.mp4
```

Pass `preview.png --preview` in place of the MP4 path to render the invoice
request shot as a PNG. Pass `--blender` or `--ffmpeg` if the executable is
installed in a custom location.

The film runs for 36 seconds and has an original instrumental score and
on-screen captions. Blender renders the models, gestures, and camera moves
locally. FFmpeg encodes the frames and score into a single MP4.

## Adapt it

Copy `storyboard.json` and pass your copy with `--storyboard` to change the
six titles and captions. Each shot is six seconds. Edit `scene.py` to change
the characters, props, or timing and `score.py` to change the soundtrack.

Parent project: [Glean System vision explainer video](../../video/).
Related editing proposal: [#8](https://github.com/pistoljosh-ai/Glean-Commons/issues/8).
