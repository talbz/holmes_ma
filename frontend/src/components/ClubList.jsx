import React from 'react';
import { memo } from 'react';
import classNames from 'classnames';
import PropTypes from 'prop-types';

export const ClubList = memo(({ clubs, selectedClub, onSelectClub, clubStatuses }) => {
  return (
    <div className="clubs-list">
      <h3>סניפים זמינים</h3>
      <div className="clubs-grid">
        {clubs.map((club) => {
          const status = clubStatuses[club] || 'idle';
          console.log(`Club: "${club}", Status: "${status}"`);
          
          return (
            <div 
              key={club}
              className={classNames('club-item', {
                'club-item-selected': selectedClub === club,
                'club-item-processing': status === 'processing',
                'club-item-success': status === 'success',
                'club-item-failed': status === 'failed'
              })}
              onClick={() => onSelectClub(club)}
            >
              <span className="club-item-text">{club}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
});

ClubList.displayName = 'ClubList';

ClubList.propTypes = {
  clubs: PropTypes.arrayOf(PropTypes.string).isRequired,
  selectedClub: PropTypes.string,
  onSelectClub: PropTypes.func.isRequired,
  clubStatuses: PropTypes.object,
}; 