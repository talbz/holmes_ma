import React from 'react';
import PropTypes from 'prop-types';
import '../styles/CrawlerControls.scss';

export const CrawlerControls = ({ 
  crawlStatus, 
  onStartCrawl, 
  onStopCrawl, 
  headlessMode, 
  onHeadlessToggle
}) => {
  return (
    <>
      {/* Crawler status display */}
      {crawlStatus?.inProgress && (
        <div className="crawler-status">
          <h3>איסוף נתונים בתהליך...</h3>
          <p className="status-message">{crawlStatus.message}</p>
          
          {/* Add current club and day information if available */}
          {crawlStatus.currentClub && (
            <p className="current-club">
              סניף נוכחי: {crawlStatus.currentClub} 
              {crawlStatus.currentClubIndex !== undefined && crawlStatus.totalClubs && 
                ` (${crawlStatus.currentClubIndex + 1} מתוך ${crawlStatus.totalClubs})`
              }
            </p>
          )}
          
          {crawlStatus.currentDay && (
            <p className="current-day">יום נוכחי: {crawlStatus.currentDay}</p>
          )}
          
          <div className="progress-container">
            <div 
              className="progress-bar" 
              style={{ width: `${crawlStatus.progress}%` }}
            />
            <span className="progress-text">{Math.round(crawlStatus.progress)}%</span>
          </div>
          
          {/* Add stop button directly in the status display for visibility */}
          <button 
            className="crawl-button stop-button crawler-status-stop" 
            onClick={onStopCrawl}
          >
            עצור איסוף נתונים
          </button>
        </div>
      )}
      
      {/* Crawl completion indicator - Shown briefly after crawl completes */}
      {!crawlStatus?.inProgress && crawlStatus?.lastCompleted && (
        <div className="crawler-status crawler-status-complete">
          <h3>איסוף נתונים הסתיים!</h3>
          <p>נאספו נתונים מ-{crawlStatus.processedClubs || 0} סניפים.</p>
          <p className="completion-time">זמן סיום: {new Date(crawlStatus.lastCompleted).toLocaleTimeString()}</p>
        </div>
      )}
      
      {/* Crawl Controls Section */}
      <section className="controls-section">
        <h2>בקרת איסוף נתונים</h2>
        <div className="controls">
          <div className="crawl-controls">
            <button 
              className="crawl-button start-button" 
              onClick={onStartCrawl}
              disabled={crawlStatus?.inProgress}
            >
              {crawlStatus?.inProgress ? 'איסוף נתונים בתהליך...' : 'התחל איסוף נתונים'}
            </button>
            
            {/* Show stop button only during active crawl */}
            {crawlStatus?.inProgress && (
              <button 
                className="crawl-button stop-button" 
                onClick={onStopCrawl}
              >
                עצור איסוף
              </button>
            )}
            
            <div className="headless-toggle">
              <label className="toggle-switch">
                <input 
                  type="checkbox" 
                  checked={headlessMode} 
                  onChange={onHeadlessToggle}
                  disabled={crawlStatus?.inProgress} // Disable toggle during crawl
                />
                <span className="slider round"></span>
              </label>
              <span>מצב ללא ממשק ({headlessMode ? 'מופעל' : 'כבוי'})</span>
            </div>
          </div>
        </div>
      </section>
    </>
  );
};

CrawlerControls.propTypes = {
  crawlStatus: PropTypes.shape({
    inProgress: PropTypes.bool,
    currentClub: PropTypes.string,
    currentDay: PropTypes.string,
    progress: PropTypes.number,
    message: PropTypes.string,
    totalClubs: PropTypes.number,
    currentClubIndex: PropTypes.number,
    lastCompleted: PropTypes.string,
    processedClubs: PropTypes.number
  }),
  onStartCrawl: PropTypes.func.isRequired,
  onStopCrawl: PropTypes.func.isRequired,
  headlessMode: PropTypes.bool.isRequired,
  onHeadlessToggle: PropTypes.func.isRequired
}; 