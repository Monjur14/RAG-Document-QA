# Frontend

React + TypeScript single-page app for the Document Q&A backend. Built with Vite and Tailwind CSS.

## Run

Needs Node.js 22.22 or newer (`node -v`). Start the backend first (`uvicorn app.main:app --reload` in `backend/`), then:

```bash
npm install
npm run dev        # http://localhost:5173
```

The dev server forwards `/api/*` to `http://localhost:8000`, so the browser only talks to one origin and the
backend needs no CORS setup. Point it elsewhere with `API_URL=http://host:port npm run dev`.

The npm scripts call `node node_modules/...` directly instead of the usual `vite` / `vitest` shortcuts. On Windows,
npm runs those shortcuts through `cmd.exe`, which breaks when the project path contains `&` (as in `RAG Document Q&A`).
Calling node directly works in any folder and any shell.

## Other commands

```bash
npm test           # Vitest + Testing Library
npm run build      # type check and build static files into dist/
npm run lint       # oxlint
```

`/design` shows the color tokens and shared components. It exists in development only.

## Layout

```
src/
  api/          fetch wrapper (client.ts), response types (types.ts), TanStack Query hooks (hooks.ts)
  components/   layout, status badges, page header, skeletons
  pages/        one file per route: Library, Chat, Metrics, plus 404 and the dev-only design page
  index.css     design tokens: every color, font and easing curve lives here
```

## Security

Answers and passages come from an LLM and from uploaded documents, so they are untrusted. They are always
rendered as plain text: there is no `dangerouslySetInnerHTML`, no Markdown renderer, and no links built from
document text. The frontend holds no API keys; it only talks to the backend.
