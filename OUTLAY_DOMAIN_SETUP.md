# Outlay — domain & deploy setup (outlay.ai)

Everything needed to move the site from `modelpilot.pages.dev` to **outlay.ai**.
The DNS/registrar steps are yours (I can't touch your Cloudflare account); the
in-repo changes are pre-staged below so the swap is one commit when the domain
resolves.

## 0. Before you buy
- **Trademark check** — do a quick USPTO/TESS (or local) search for "Outlay" in
  software/finance classes (9, 35, 42). Our diligence found no prominent
  finance/software namesake, but confirm before committing.
- **Registrar** — `outlay.com` is likely taken (common word); plan on
  **outlay.ai** (and grab `getoutlay.com` / `outlay.app` as redirects if cheap).
  Prefer **Cloudflare Registrar** since the site is already on Cloudflare Pages —
  it auto-wires DNS and avoids markup.

## 1. Point outlay.ai at the existing Pages project (simplest)
Keeps the current "modelpilot" Pages project; just serves it on the new domain.
1. Cloudflare dash → **Workers & Pages → modelpilot → Custom domains → Set up a
   custom domain** → add `outlay.ai` and `www.outlay.ai`.
2. If the domain is on Cloudflare, DNS + SSL are created automatically. If it's
   at another registrar, add a **CNAME** `outlay.ai → modelpilot.pages.dev`
   (use a CNAME-flattened root, or an `ALIAS`/`ANAME` if your DNS supports it).
3. Wait for the cert to issue (minutes). `outlay.ai` now serves the site.

## 2. (Optional, cleaner) Fresh "outlay" Pages project
If you want the default preview URLs to read `outlay.pages.dev`:
1. Create a new Pages project named **outlay**, connected to this repo, build
   output `./modelpilot/site` (same as today — see `wrangler.toml`).
2. Add `outlay.ai` as its custom domain.
3. Decommission the `modelpilot` project's production domain (or 301 it — step 4).
> Tradeoff: a rename gives clean URLs but means re-adding the Cloudflare build
> integration. Option 1 is faster; do option 2 only if the `modelpilot.pages.dev`
> preview URLs bother you. (`wrangler.toml` `name` would change to `outlay`.)

## 3. Redirect the old domain (optional but recommended)
Add `modelpilot/site/_redirects` (Cloudflare Pages honors it):
```
https://modelpilot.pages.dev/* https://outlay.ai/:splat 301
```
Keeps old links/SEO alive and forwards them to the new brand.

## 4. Flip the in-repo URLs (do this once outlay.ai resolves — not before)
Premature canonical/OG changes hurt SEO, so leave these until the domain is live,
then run:
```bash
# updates canonical + og:url + any absolute self-links across the site
grep -rl "modelpilot.pages.dev" modelpilot/site --include=*.html \
  | xargs sed -i 's#https://modelpilot.pages.dev#https://outlay.ai#g'
```
Review the diff (the console/login/signup links point at
`modelpilot-console-prod.fly.dev` — those are the optimization-engine app and
should **stay** until/unless that app is also rebranded). Commit + merge to ship.

## 5. Email (later)
For credibility, set up `hello@outlay.ai` (Cloudflare Email Routing → forward to
your inbox) and swap the `mailto:krethikram@gmail.com` CTAs to it. One sed when
ready:
```bash
grep -rl "krethikram@gmail.com" modelpilot/site --include=*.html \
  | xargs sed -i 's/krethikram@gmail.com/hello@outlay.ai/g'
```

## Checklist
- [ ] Trademark sweep (classes 9/35/42)
- [ ] Register outlay.ai (+ defensive variants)
- [ ] Custom domain on Pages (option 1 or 2) → cert issued
- [ ] `_redirects` from modelpilot.pages.dev → outlay.ai
- [ ] Flip canonical/OG URLs (step 4) once live
- [ ] (later) hello@outlay.ai + swap mailto CTAs
