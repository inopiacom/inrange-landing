# inrange-landing

> **Publishing:** the site is served by **GitHub Pages straight from `main`**
> (apex A records → 185.199.108–111.153, `www` → `inopiacom.github.io`).
> Anything merged to `main` is live within minutes. The Cloudflare notes
> further down are historical; `_headers` and `wrangler.toml` are not used.
>
> **App Store switch:** `appstore.js` holds `APP_STORE_LIVE`. While `false`,
> pages say "Coming soon to the App Store" and invite pages keep TestFlight.
> Flip it to `true` once inRange is released to show Apple's badge and
> point every install step at https://apps.apple.com/app/id6788735095.

Static landing page for **inRange AI** — served from `https://getinrange.ai` (and `https://getinrange.com` → 301 redirect to `.ai`).

## Structure

```
inrange-landing/
├── wrangler.toml       # Cloudflare Workers Static Assets config
├── public/             # Everything served on the public URL
│   ├── index.html      # Hero + features + screenshots + pricing + download + FAQ
│   ├── privacy.html    # Placeholder privacy policy
│   ├── terms.html      # Placeholder terms of service
│   ├── security.html   # Security posture + vuln-disclosure
│   ├── styles.css      # Liquid Glass-inspired minimal CSS
│   ├── main.js         # Waitlist form handler (Formspree wired to xdarwprw)
│   ├── _headers        # Security headers (CSP, HSTS, etc.)
│   ├── robots.txt      # SEO
│   └── sitemap.xml     # SEO
└── README.md
```

## Local preview

```bash
cd public && python3 -m http.server 8080
open http://localhost:8080
```

## Deploy to Cloudflare Pages

1. Log in to Cloudflare Dashboard → Workers & Pages
2. Create a new Pages project → **Connect to Git** → select `inopiacom/inrange-landing`
3. Framework preset: **None** (this is plain HTML)
4. Build command: *(empty)*
5. Build output directory: `/`
6. Deploy

Cloudflare picks up `_headers` and `_redirects` automatically.

Once the domains are live at Loopia:

- Add CNAME `getinrange.ai` → `<project>.pages.dev`
- Add CNAME `www.getinrange.ai` → `<project>.pages.dev`
- Add CNAME `getinrange.com` → `<project>.pages.dev` (redirect handled by `_redirects`)

## Waitlist form

Update `action="https://formspree.io/f/REPLACE_ME"` in `index.html` with your Formspree endpoint.

**Alternatives:**
- **Loops.so** — good deliverability, native email marketing. Change form to `POST https://app.loops.so/api/newsletter-form/<listId>` with `Content-Type: application/json`.
- **Beehiiv** — same idea, free tier.
- **Cloudflare Workers + KV** — full self-hosted, ~10 lines of Workers code. Handles waitlist storage directly.

## What's placeholder

- Formspree endpoint (`REPLACE_ME`)
- Privacy, Terms, Security pages contain short placeholder text
- `og.png` for social preview — needs to be added (1200×630px)
- No favicon yet

## License

Proprietary © 2026 Inopia AB.
