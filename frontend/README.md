# CofC Soccer Analytics Frontend

React/Vite dashboard for team analytics, COUG Table views, and the private
staff prototype.

## Local configuration

Create `frontend/.env.local` when overrides are needed:

```text
VITE_API_URL=http://localhost:8000
VITE_ACTIVE_SEASON=2026
VITE_STAFF_PASSCODE=<local demo passcode>
```

The COUG Table reads the active season from `/api/seasons`. The frontend
variable is a startup/failure fallback and should match
`configs/organizations/cofc.json`. Historical seasons remain selectable.
The staff prediction simulator reads its matches from `/api/schedule`; update
the tracked season CSV rather than adding matches directly to React.

## Commands

```bash
npm install
npm run dev
npm run build
npm run lint
```

## Vite notes

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
