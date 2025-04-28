import React from 'react';
import { memo, useMemo } from 'react';
import classNames from 'classnames';
import PropTypes from 'prop-types';
import '../styles/CrawlerStatus.scss';

export const CrawlerStatus = memo(({ status, isError }) => {
  const {
    inProgress,
    message,
    currentClub,
    currentDay,
    totalClubs,
    currentClubIndex,
    progress,
  } = status;

  const progressPercentage = useMemo(() => {
    if (progress !== undefined) return progress;
    if (totalClubs && currentClubIndex !== undefined) {
      return Math.floor((currentClubIndex / totalClubs) * 100);
    }
    return 0;
  }, [progress, totalClubs, currentClubIndex]);

  const progressClass = useMemo(() => {
    return classNames('progress-bar', {
      'progress-low': progressPercentage < 33,
      'progress-medium': progressPercentage >= 33 && progressPercentage < 66,
      'progress-high': progressPercentage >= 66
    });
  }, [progressPercentage]);

  const statusClass = classNames('crawler-status', {
    'crawler-status-in-progress': inProgress,
    'crawler-status-error': isError && !inProgress,
    'crawler-status-complete': !inProgress && !isError && message?.includes('הסתיים'),
  });

  return (
    <div className={statusClass}>
      <h3>סטטוס איסוף נתונים</h3>
      <div className="status-container">
        <div className="status-message">
          {inProgress ? 'איסוף נתונים מתבצע כעת...' : 'איסוף נתונים הסתיים'}
        </div>

        {message && (
          <div className="status-detail">{message}</div>
        )}

        {currentClub && (
          <div className="status-detail">
            סניף נוכחי: {currentClub} {currentClubIndex !== undefined && totalClubs && `(${currentClubIndex + 1}/${totalClubs})`}
          </div>
        )}

        {currentDay && (
          <div className="status-detail">
            יום נוכחי: {currentDay}
          </div>
        )}

        {(inProgress || progressPercentage > 0) && (
          <div className="progress-bar-container">
            <div 
              className={progressClass}
              style={{ width: `${progressPercentage}%` }}
              role="progressbar"
              aria-valuenow={progressPercentage}
              aria-valuemin="0"
              aria-valuemax="100"
            />
            <div className="progress-text">{progressPercentage}%</div>
          </div>
        )}
      </div>
    </div>
  );
});

CrawlerStatus.displayName = 'CrawlerStatus';

CrawlerStatus.propTypes = {
  status: PropTypes.shape({
    inProgress: PropTypes.bool,
    message: PropTypes.string,
    currentClub: PropTypes.string,
    currentDay: PropTypes.string,
    totalClubs: PropTypes.number,
    currentClubIndex: PropTypes.number,
    progress: PropTypes.number,
  }).isRequired,
  isError: PropTypes.bool,
}; 