This project contains the letters between my maternal grandparents, Wilhelm and Marianne Kellermann (their daughter Helga, born in 1940, is my mother), during his service in the German army in WWII. See README.md for more information and a summary of the content.

The goal ultimately is to share their story in multiple media formats:
- An interactive website (in German and English)
- Printed books (in seaprate German and English editions)

But we're working one step at a time, we're not one-shotting this.

We're going to keep the primary content source (the `kriegstagebuch-*.txt` files) in the original German, and any changes we make to it (e.g. formatting, fixing OCR errors, etc.) MUST preserve the original intent as much as possible (including preserving abbreviations, contemporary place names, etc.). We are not going to apply any editorial voice to Wilhelm's content - technical fixes only!

Note that the marker ">>>>>" in the .txt files indicates the extent of my manual proofreading review. Ignore it.

The marker "#####" indicates a note regarding ambiguous OCR reconstruction or an unknown abbreviation.

The marker "&&&&&" indicates a brief annotation that summarizes the broader historical context of events, places, or people referenced in the surrounding letter text — e.g. naming a campaign or operation and giving a one-or-two-sentence sketch. These annotations stay short on purpose: they are stubs that downstream tooling will later expand into more detailed, linked historical content shown in the map web app. Multiple letters can refer to the same broader topic, so each `&&&&&` annotation should be specific to *how* that letter touches the topic — not a full encyclopedia entry. They are derived content, not part of Wilhelm's original transcription, and like `#####` they live as their own paragraph (separated from surrounding text by blank lines).

Any content we **derive** from the original source material will be in both German and English (stored in /data/de-DE or /data/en-US, respectively). Whenever possible we will preserve Wilhem's editorial voice (including contemporary terminology), but we have more leeway here, especially in the English translation.

Any code, data, schemas, etc. that is independent of the content will all be in English only. And our chat interactions will be primarily in English, but I know German so feel free to use German where appropriate, e.g. when quoting the text.

## Website principles

These guide every change to the interactive website. New principles get added here as they come up.

- **Instant language switch.** Toggling DE/EN is a pure client-side text swap that preserves *all* UI state — map zoom and pan, chapter filter, marker hover/click selection, open detail panes, scroll position. No re-fetch, no re-render of stateful widgets, no flash. Both languages are loaded into the client whenever content data is requested, so the swap can be instant.
  - We may later add per-element language overrides, but the global switch must remain instant and lossless.
  - Identifiers that bridge across languages (chapter numbers, chronology global indices, lat/lon coordinates) must stay stable so a UI element rendered in DE can be re-rendered in EN by looking up the matching record by ID.
