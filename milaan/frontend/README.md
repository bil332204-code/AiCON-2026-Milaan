# Milaan website and workspace

Plain HTML, CSS and ES modules in `dist/`, served by the FastAPI backend (no build step). Run the backend as described in the root [README](../../README.md) and open http://127.0.0.1:8000.

| File | Purpose |
|---|---|
| `index.html` | Landing page, workspace shell and the in-app guide (English / Roman Urdu) |
| `app.js` | Workspace views, results table, review drawer, sample shop |
| `backend-ui.js` | Sign-in, batches, uploads and saved-batch actions |
| `seller-flow.js` | New-batch dialog, paste-orders parser, statement PDF check dialog and the three-step batch view |
| `milaan-api.js` | API client |
| `engine.js` | Matching rules used by the in-browser sample shop |
| `import-preview.js` | Column mapping preview for CSV uploads |
| `cinematic.js`, `scene.js` | Landing page animation |
| `styles.css`, `cinematic.css`, `phase1.css`, `seller.css` | Styles |
| `about.html`, `privacy.html`, `terms.html` | Public pages |

Tests: `npm test` (Node's built-in test runner) and `npm run check` (syntax check).
