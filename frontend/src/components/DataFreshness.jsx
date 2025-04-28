import React from 'react';
import PropTypes from 'prop-types';
import { memo } from 'react';

export const DataFreshness = memo(({ dataInfo, onStartCrawl }) => {
  // If no data at all, show a stronger warning
  if (!dataInfo.has_data) {
    return (
      <div className="data-freshness-warning stale-data">
        <div className="warning-icon">⚠️</div>
        <div className="warning-content">
          <h3>אין נתונים זמינים</h3>
          <p>לא נמצאו נתונים במערכת. יש לבצע איסוף נתונים לפני השימוש באפליקציה.</p>
          <button 
            className="crawl-button start-button data-refresh-button"
            onClick={onStartCrawl}
          >
            איסוף נתונים עכשיו
          </button>
        </div>
      </div>
    );
  }

  // If data is older than 7 days, show staleness warning
  if (dataInfo.is_stale) {
    return (
      <div className="data-freshness-warning stale-data">
        <div className="warning-icon">⚠️</div>
        <div className="warning-content">
          <h3>מידע לא עדכני</h3>
          <p>
            המידע המוצג נאסף לפני {dataInfo.days_since_crawl} ימים 
            ({new Date(dataInfo.latest_crawl_date).toLocaleDateString()})
            ועשוי להיות לא מדויק. מומלץ לבצע איסוף נתונים חדש.
          </p>
          <button 
            className="crawl-button start-button data-refresh-button"
            onClick={onStartCrawl}
          >
            איסוף נתונים עכשיו
          </button>
        </div>
      </div>
    );
  }

  // Data is fresh (less than a week old)
  return (
    <div className="data-freshness-info fresh-data">
      <div className="info-icon">✓</div>
      <div className="info-content">
        <p>
          המידע עדכני ונאסף לפני {dataInfo.days_since_crawl} ימים
          ({new Date(dataInfo.latest_crawl_date).toLocaleDateString()})
          {dataInfo.is_complete_crawl === false && 
            <span className="partial-crawl-indicator"> - נתונים חלקיים בלבד</span>
          }
        </p>
      </div>
    </div>
  );
});

DataFreshness.displayName = 'DataFreshness';

DataFreshness.propTypes = {
  dataInfo: PropTypes.shape({
    has_data: PropTypes.bool,
    latest_file: PropTypes.string,
    latest_crawl_date: PropTypes.string,
    days_since_crawl: PropTypes.number,
    is_stale: PropTypes.bool,
    is_complete_crawl: PropTypes.bool
  }).isRequired,
  onStartCrawl: PropTypes.func.isRequired
}; 