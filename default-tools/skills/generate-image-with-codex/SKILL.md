---
name: generate-image-with-codex
description: Generate images from a text description using the locally installed Codex CLI's built-in image generation. Use this skill whenever the user asks to generate, create, make, draw, render, or produce an image, picture, illustration, logo, icon, banner, sticker, avatar, or any visual artwork from a text prompt — even if they never mention Codex. Triggers on requests like "generate an image of a mountain at sunset", "make me a picture of a cat", "create a logo for my coffee shop", "draw a cartoon robot", or "I need an icon for my app". Do not try to satisfy these requests any other way — Claude cannot generate images itself, and this skill is the supported path.
---

# Generate Image with Codex

Claude has no native image generation. The Codex CLI installed on this machine
does — it ships a stable `image_generation` tool. This skill drives `codex exec`
non-interactively to turn a text description into an image file and deliver it
where the user wants it.

## When to use

Any request to *produce* a new image from a description: "generate an image
of…", "make a logo for…", "draw a…", "create an icon/banner/avatar…".

This skill is **not** for editing, analyzing, or describing an image the user
already has — only for generating new ones.

## Prerequisites

The `codex` CLI must be installed and authenticated. The bundled script checks
for it and fails clearly if it is missing. If Codex is unavailable, tell the
user to install and authenticate the Codex CLI — do not attempt to generate the
image some other way, and do not claim an image was produced when it was not.

## Workflow

### 1. Settle the prompt and destination

Make sure you have a concrete image description. If the request is vague
("make me a logo"), ask one short clarifying question — subject, style, mood —
rather than guessing blindly.

Then ask the user where to save the result, with the current working directory
as the default:

> Where would you like the image saved? (default: the current directory)

Keep this to a single brief question. Do not interrogate the user.

### 2. Generate

Run the bundled script with the image description as one quoted argument:

```bash
"${CLAUDE_PLUGIN_ROOT}/skills/generate-image-with-codex/scripts/generate_image.sh" "a watercolor fox sitting in autumn leaves"
```

The script invokes `codex exec`, waits for Codex to produce the image, and
prints the absolute path of every generated file (newest first). Generation
usually takes 30–90 seconds — let it run, do not kill it early.

If the script exits non-zero, read its stderr and relay the actual problem to
the user (Codex not installed, not authenticated, or no image produced). Do not
paper over a failure.

### 3. Deliver

For each path the script printed:

1. Copy the file from the Codex cache to the destination the user chose. Give
   it a descriptive kebab-case name derived from the prompt
   (e.g. `watercolor-fox-autumn.png`). If that name already exists, add a
   numeric suffix (`-2`, `-3`, …) rather than overwriting.
2. Show the user the result by using the Read tool on the copied file so the
   image renders inline in the conversation.
3. Report the final saved path.

If Codex returned more than one image for a single request, deliver all of them.

## Notes

- Codex saves originals to `~/.codex/generated_images/<thread-id>/`. The skill
  copies them out; leave the originals in place as a cache.
- The script passes `--skip-git-repo-check`, so it works from any directory.
- Image generation is non-deterministic — the same prompt yields different
  images each run. If the user dislikes a result, just run the script again.
