# Holmes Place Schedule Application

This application provides a user-friendly way to view and filter Holmes Place fitness clubs' class schedules. It consists of a FastAPI backend with WebSocket support and a React frontend.

## Features

- Web crawler that fetches class schedules from the Holmes Place website
- Real-time updates via WebSocket during crawling
- Filter classes by name, instructor, day, time, and club
- Modern UI with responsive design
- Toast notifications for user feedback

## Project Structure

```
holmes_crawler/
├── backend/           # Python FastAPI backend
│   ├── app.py         # Main API endpoints and WebSocket server
│   ├── crawler.py     # Web crawler for Holmes Place website
│   └── data/          # Data storage for crawled schedules
├── frontend/          # React frontend
│   ├── src/           # Source code
│   │   ├── components/# React components
│   │   ├── hooks/     # Custom React hooks
│   │   ├── styles/    # SCSS styles
│   │   ├── App.jsx    # Main App component
│   │   └── index.jsx  # Entry point
│   ├── index.html     # HTML template
│   └── package.json   # Dependencies and scripts
└── README.md          # Project documentation
```

## Setup and Installation

### Backend

1. Make sure you have Python 3.7+ installed
2. Install dependencies:
   ```bash
   cd backend
   pip install fastapi uvicorn websockets playwright
   playwright install
   ```
3. Run the backend server:
   ```bash
   python app.py
   ```

### Frontend

1. Make sure you have Node.js 14+ installed
2. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```
3. Run the frontend development server:
   ```bash
   npm start
   ```

## Usage

1. Access the web application at http://localhost:1234
2. Click the "התחל איסוף נתונים" (Start Data Collection) button to begin crawling
3. Monitor the crawling process with real-time updates
4. Once crawling is complete, use the filters to find specific classes
5. Click on a club in the club list to filter classes by that club

## Technologies Used

- **Backend**:
  - FastAPI: Fast, modern Python web framework
  - WebSockets: For real-time communication
  - Playwright: For browser automation and crawling
  
- **Frontend**:
  - React: UI library
  - React Query: Data fetching and state management
  - SCSS: For styling
  - Parcel: For bundling and development

## License

This project is released under the MIT License. 