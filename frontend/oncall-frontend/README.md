# OffCall AI frontend

React + TypeScript single-page app. See the [root README](../../README.md) for
the full picture.

## Running it

```bash
cp .env.example .env     # set REACT_APP_API_URL if the API is not on :8000
npm ci
npm start                # dev server on http://localhost:3000
```

```bash
npm run build            # production bundle into build/
npm test                 # CRA test runner
npm run lint             # eslint over src/
```

`REACT_APP_API_URL` is read **at build time**, so rebuild after changing it.
The Docker image takes it as a build arg:

```bash
docker build --build-arg REACT_APP_API_URL=https://api.example.com/api/v1 -t offcall-frontend .
```

## Layout

```
src/
  App.tsx            hand-rolled router: Page union, PAGE_PATHS, resolvePath
  components/        64 feature components, one per screen
  components/ui/     17 local UI primitives (no component library)
  contexts/          AuthContext, NotificationContext
  hooks/             theme, sidebar preferences
  config/api.ts      API base URL
  services/          API helpers
```

There is no react-router: `App.tsx` maps `window.location.pathname` to a `Page`
and handles `popstate` itself. To add a screen, add the page to the `Page`
union, give it an entry in `PAGE_PATHS`, and render it from
`renderSidebarPageContent`.

## Styling

Tailwind with a dark, near-black palette defined as CSS variables in
`src/index.css`. Conventions: cards are transparent with `border-white/[0.06]`,
body text is `text-[13px] text-zinc-400`, headings are `text-white
text-[15px] font-medium`. No gradients, shadows or glows.

## Known issues

`npm run build` reports roughly 130 unused-import warnings and 13
`react-hooks/exhaustive-deps` warnings. The build does not treat warnings as
errors, so it passes; clearing them is a welcome contribution. Note that
`exhaustive-deps` fixes can change behaviour, so do those carefully and in
small batches.
