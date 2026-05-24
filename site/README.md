# Skydock website

Astro static site for the Skydock landing page. Auto-deploys to GitHub Pages
via `.github/workflows/deploy-site.yml` on push to `main` when files under
`site/` change.

## Local development

```sh
npm install
npm run dev      # http://localhost:4321
npm run build    # output: dist/
npm run preview  # serve dist/ locally
```

## Updating the simulation demo

The hero asset is `public/sim_demo.gif`, generated from the Python sim:

```sh
cd ../skydock
python run.py --save ../site/public/sim_demo.gif \
  --set simulation.duration_hours=0.25 \
  --vehicles 1 --seed 7 \
  --set animation.fps=12
```

For a longer / multi-vehicle clip, increase `duration_hours` and `--vehicles`,
but matplotlib buffers all frames in memory before encoding the GIF —
multi-hour clips at default DPI can OOM (saw 5.8 GB at 1.5h × 3 vehicles).
With `ffmpeg` installed, switching the save target to `.mp4` is faster and
produces a smaller file.

## Deploy

GitHub Pages must be enabled for this repo: **Settings → Pages → Source:
GitHub Actions**. The first deploy will create the `github-pages`
environment automatically.

Live URL (once deployed): https://krethikram-sudo.github.io/options-bot/

## Customizing

- **Founder bio:** Replace the placeholder paragraph in `src/pages/index.astro`
  inside `<div class="contact-card">`. Search for `TODO(krethik)`.
- **Add LinkedIn / GitHub / Twitter links:** Uncomment and edit the
  `contact-links` block in `src/pages/index.astro`.
- **Custom domain:** Add a `CNAME` file to `public/` containing your domain
  (e.g. `skydock.ai`) and configure DNS. Then remove `base: '/options-bot'`
  from `astro.config.mjs` and update `site` to your domain.
