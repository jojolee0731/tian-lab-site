# Tian Lab Website

Tian Lab public website prototype: static, fast, multilingual, and data-driven.

## Local Preview

Run from this folder:

```bash
npm run dev
```

Open:

```text
http://localhost:4173/
```

The site is static. It can also run with:

```bash
python3 -m http.server 4173 --bind 127.0.0.1
```

## If localhost does not open

1. Confirm the server is running:

```bash
lsof -nP -iTCP:4173 -sTCP:LISTEN
```

2. If nothing is listening, start it again with `npm run dev`.
3. If another process owns the port, stop that process or run:

```bash
python3 -m http.server 4174 --bind 127.0.0.1
```

Then open `http://localhost:4174/`.

## Editing Content

Most public-facing content lives in:

```text
data/site.json
```

Use that single file to update:

- research tracks
- publications and DOI links
- cover gallery
- people placeholders and alumni
- news items
- English / Chinese / Spanish copy

Images live in:

```text
assets/images/
```

## Current Public Sections

- Home: full-screen drummer hero, lab claim, CTA, rhythm canvas
- Research: five research tracks with claims and capability bullets
- Publications: representative works with journal, year, author abbreviations, DOI links
- Covers & Visual Stories: STTT, Chem Soc Rev, Analytical Chemistry, MedComm, Advanced Materials
- Collaboration: IBEC Molecular Bionics and Adcerebri as a translational platform
- People / Join / Contact: structured placeholders ready for later table import

## Deployment Notes

- GitHub Pages: deploy the folder as a static site.
- Vercel: import the folder and use no build command.
- Current GitHub Pages target: `https://jojolee0731.github.io/tian-lab-site/`.
