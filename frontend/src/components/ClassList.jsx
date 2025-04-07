import React from 'react';
import PropTypes from 'prop-types';
import { memo } from 'react';
import classNames from 'classnames';

// Assuming classes is an array like [{ name: ..., time: ..., club: ..., region: ... }, ...]
// And regions is a sorted array like ["צפון", "מרכז", "דרום", ...]
export const ClassList = memo(({ classes = [], regions = [] }) => {

  // Group classes by region first
  const classesByRegion = classes.reduce((acc, currentClass) => {
    const region = currentClass.region || 'לא ידוע';
    if (!acc[region]) {
      acc[region] = [];
    }
    acc[region].push(currentClass);
    return acc;
  }, {});

  // Group classes by club within each region
  const groupedClasses = {};
  regions.forEach(region => {
    if (classesByRegion[region]) {
       groupedClasses[region] = classesByRegion[region].reduce((acc, currentClass) => {
          const club = currentClass.club || 'לא ידוע';
          if (!acc[club]) {
              acc[club] = [];
          }
          acc[club].push(currentClass);
          // Sort classes within each club by Day (YYYY-MM-DD) then Time (HH:MM)
          acc[club].sort((a, b) => {
              const dayCompare = (a.day || '').localeCompare(b.day || '');
              if (dayCompare !== 0) {
                  return dayCompare;
              }
              // If days are the same, compare by time
              return (a.time || '').localeCompare(b.time || '');
          });
          return acc;
       }, {});
    }
  });

  if (!classes || classes.length === 0) {
    return <div className="empty-message">לא נמצאו שיעורים מתאימים</div>;
  }

  return (
    <div className="classes-grouped-list">
      {regions.map(region => (
        groupedClasses[region] && Object.keys(groupedClasses[region]).length > 0 && (
          <div key={region} className="region-group">
            <h3 className="region-title">{region}</h3>
            <div className="clubs-container-for-region">
              {Object.entries(groupedClasses[region]).map(([clubName, clubClasses]) => {
                // Clean up club name for display
                const displayClubName = clubName
                  .replace("הולמס פלייס ", "")
                  .replace("גו אקטיב ", "")
                  .replace("פרימיום ", "") // Also remove premium?
                  .replace("פמילי ", "") // Also remove family?
                  .trim();
                
                return (
                  <div key={clubName} className="club-group">
                    <h4 className="club-title">{displayClubName}</h4>
                    <div className="classes-grid">
                      {clubClasses.map((cls, index) => {
                        // --- Past Class Logic --- 
                        let isPast = false;
                        let classDateTimeStr = null;
                        if (cls.day && cls.time) {
                          // Combine date and time for comparison (assuming local timezone is appropriate)
                          // Format: YYYY-MM-DDTHH:MM:00 
                          classDateTimeStr = `${cls.day}T${cls.time}:00`; 
                          try {
                            const classDateTime = new Date(classDateTimeStr);
                            const now = new Date();
                            // Check if the date object is valid before comparing
                            if (!isNaN(classDateTime.getTime()) && classDateTime < now) {
                              isPast = true;
                            }
                          } catch (e) {
                            console.error("Error parsing class date/time:", classDateTimeStr, e);
                          }
                        }
                        // ------------------------

                        // --- Format Date D.M (remains same) --- 
                        let displayDateDM = '-';
                        if (cls.day) {
                          try {
                            const parts = cls.day.split('-'); // YYYY-MM-DD
                            if (parts.length === 3) {
                              const dayOfMonth = parseInt(parts[2], 10);
                              const month = parseInt(parts[1], 10);
                              displayDateDM = `${dayOfMonth}.${month}`;
                            }
                          } catch (e) { /* Ignore */ }
                        }
                        // ---------------------------------------

                        return (
                          <div 
                            key={`${cls.day}-${cls.time}-${cls.name}-${index}`} 
                            className={classNames('class-card', { 'class-card--past': isPast })}
                          >
                            {/* --- Line 1: Time DayName D.M (Past) --- */}
                            <p className="class-card-line1">
                                <span className="time">{cls.time || '--:--'}</span>
                                <span className="day-name">{cls.day_name_hebrew || ''}</span>
                                <span className="date-dm">{displayDateDM}</span>
                                {isPast && <span className="past-indicator">(חלף)</span>}
                            </p>
                            {/* --- Line 2: Name - Instructor --- */}
                            <p className="class-card-line2">
                                <span className="name">{cls.name}</span>
                                {cls.instructor && <span className="instructor"> - {cls.instructor}</span>}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )
      ))}
    </div>
  );
});

ClassList.displayName = 'ClassList';

ClassList.propTypes = {
  classes: PropTypes.arrayOf(PropTypes.shape({
      club: PropTypes.string,
      day: PropTypes.string, 
      day_name_hebrew: PropTypes.string,
      time: PropTypes.string,
      name: PropTypes.string,
      instructor: PropTypes.string,
      duration: PropTypes.string,
      location: PropTypes.string,
      region: PropTypes.string, // Added region
      timestamp: PropTypes.string
  })),
  regions: PropTypes.arrayOf(PropTypes.string) // Added regions prop
}; 