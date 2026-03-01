# Frensei Frontend

Research intelligence SaaS platform built with Next.js 14 (App Router), TypeScript, and Tailwind CSS.

## Tech Stack

- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript (strict mode)
- **Styling:** Tailwind CSS
- **UI Components:** shadcn/ui (Radix UI)
- **HTTP Client:** Axios
- **Data Fetching:** TanStack React Query
- **State:** Zustand
- **Theme:** next-themes (dark/light)
- **Linting:** ESLint + Prettier

## Project Structure

```
src/
├── app/
│   ├── (auth)/          # Auth route group (login, etc.)
│   ├── (dashboard)/     # Dashboard with sidebar layout
│   │   └── dashboard/   # /dashboard/* routes
│   └── (research)/      # Research route group
│       └── research/    # /research
├── components/
│   ├── ui/              # shadcn components
│   ├── layout/          # App layout, sidebar, header
│   ├── dashboard/       # Dashboard feature components
│   ├── timeline/        # Timeline feature components
│   ├── writing/         # Writing evolution components
│   ├── supervision/     # Supervision components
│   ├── health/          # Wellness components
│   ├── opportunities/   # Opportunities components
│   └── network/         # Network components
├── lib/
│   ├── api/             # Axios client
│   ├── hooks/           # Custom hooks
│   ├── store/           # Zustand stores
│   ├── types/           # Shared types
│   └── utils.ts
├── providers/           # React Query, Theme providers
└── services/           # API service modules
```

## Getting Started

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env.local
   # Edit .env.local - set NEXT_PUBLIC_API_URL to your backend URL
   ```

3. **Run development server:**
   ```bash
   npm run dev
   ```

4. **Build for production:**
   ```bash
   npm run build
   npm start
   ```

## Scripts

- `npm run dev` - Start development server
- `npm run build` - Production build
- `npm run start` - Start production server
- `npm run lint` - Run ESLint
- `npm run format` - Format with Prettier

## Demo Login

- **Username:** admin
- **Password:** admin123

## Core Features (7)

1. **Dashboard** - Overview and quick access
2. **Timeline** - PhD milestone tracking
3. **Writing** - Writing evolution and baseline
4. **Supervision** - Supervisor assignments
5. **Wellness** - Health check-ins
6. **Opportunities** - Recommendations
7. **Network** - Collaboration insights
