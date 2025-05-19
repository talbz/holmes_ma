# Holmes Place Crawler

A web application for crawling and displaying Holmes Place class schedules.

## Features

- Real-time crawling of Holmes Place class schedules
- WebSocket-based status updates
- Modern React frontend with real-time updates
- Data freshness indicators
- Club filtering and selection

## Setup

### Backend

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file in the backend directory with:
```
DATA_DIR=./data
```

### Frontend

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Build the frontend:
```bash
npm run build
```

## Running the Application

1. Start the backend server:
```bash
cd backend
uvicorn main:app --reload
```

2. The frontend will be served automatically by the backend at http://localhost:8000

## Data Storage

- Crawled data is stored in JSONL format in the specified data directory
- Each crawl appends to the existing data file
- The application tracks data freshness and displays appropriate warnings

## API Endpoints

- `GET /api/status` - Get current crawl status
- `POST /api/start-crawl` - Start a new crawl
- `GET /api/data` - Get the latest crawl data
- `WS /ws` - WebSocket connection for real-time updates 