# AdScribe.AI Frontend

This is the frontend application for AdScribe.AI, built with React, TypeScript, and Vite.

## Features

### Ad Analysis
- View and analyze Facebook ad campaigns
- AI-powered ad analysis with detailed insights
- Background job processing for large datasets
- Real-time job progress tracking

### Video Link Management
- **Refresh Video Links**: Automatically refresh expired Facebook video URLs
- Facebook video URLs expire after some time, so the system automatically checks and refreshes them
- Bulk refresh functionality available via the "Refresh Video Links" button in the Ad Analysis tab
- Automatic refresh when viewing individual ad analyses

### Dashboard
- Comprehensive metrics and KPI tracking
- Interactive charts and visualizations
- Date range selection with custom date picker
- "Only Analyzed Ads" filter for focused analysis

### User Management
- Secure authentication with JWT tokens
- Facebook OAuth integration
- User settings and preferences

## Getting Started

### Prerequisites
- Node.js (v18 or higher)
- npm or yarn

### Installation

1. Clone the repository
2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

4. Open your browser and navigate to `http://localhost:5173`

## Usage

### Refresh Video Links Feature

Facebook ad video URLs have expiration times and become invalid after a certain period. The application includes automatic and manual refresh capabilities:

**Automatic Refresh:**
- Video URLs are automatically checked and refreshed when viewing ad analyses
- No user intervention required - happens transparently

**Manual Refresh:**
- Use the "Refresh Video Links" button in the Ad Analysis tab
- Refreshes all expired video URLs for all your ad analyses in one operation
- Shows progress and results in a toast notification

**How it works:**
1. Click the "Refresh Video Links" button
2. The system checks all your ad analyses for expired video URLs
3. Fetches fresh URLs from Facebook API for expired ones
4. Updates the database with new URLs
5. Refreshes the ad analyses display with updated URLs

## Project Structure

```
src/
├── components/          # Reusable UI components
├── contexts/           # React contexts (Auth, Chat, etc.)
├── hooks/              # Custom React hooks
├── layouts/            # Layout components
├── pages/              # Page components
├── services/           # API services
├── types/              # TypeScript type definitions
└── utils/              # Utility functions
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Technologies Used

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Styling
- **Shadcn/ui** - UI component library
- **React Router** - Client-side routing
- **Axios** - HTTP client
- **Recharts** - Charts and visualizations
- **Lucide React** - Icons

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is proprietary software. All rights reserved.
