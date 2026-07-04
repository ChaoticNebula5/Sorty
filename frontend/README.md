# Sorty AI — Frontend

Vite + React + TypeScript frontend for the Sorty AI event media management platform.

## Development

```bash
npm install
npm run dev
```

The dev server proxies `/api` requests to `http://127.0.0.1:8000` (the FastAPI backend).

## Build

```bash
npm run build
npm run preview
```

## Structure

```
src/
├── api/          # API client, typed endpoints
├── assets/       # Static assets (images, SVGs)
├── components/
│   ├── auth/     # Admin authentication guard
│   ├── domain/   # Domain-specific components (EventCard)
│   ├── landing/  # Landing page sections
│   ├── layout/   # App shell, navigation
│   └── ui/       # Reusable UI primitives
├── lib/          # Utilities and helpers
├── pages/        # Route-level page components
├── App.tsx       # Router and route definitions
├── main.tsx      # Entry point
└── index.css     # Design tokens and global styles
```
