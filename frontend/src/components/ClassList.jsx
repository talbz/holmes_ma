import React from 'react';
import PropTypes from 'prop-types';
import { memo } from 'react';
import classNames from 'classnames';
import '../styles/ClassList.scss'; // Import component-specific styles
import { MdLocationOn, MdAccessTime, MdPerson } from 'react-icons/md';
import { format, parseISO } from 'date-fns';
import { he } from 'date-fns/locale';

// Club name mapping to short names
const clubShortNames = {
  'הולמס פלייס אשדוד': 'אשדוד',
  'הולמס פלייס באר שבע': 'באר שבע',
  'הולמס פלייס גבעתיים': 'גבעתיים',
  'הולמס פלייס הרצליה': 'הרצליה',
  'הולמס פלייס חולון': 'חולון',
  'הולמס פלייס חיפה': 'חיפה',
  'הולמס פלייס ירושלים': 'ירושלים',
  'הולמס פלייס כפר סבא': 'כפר סבא',
  'הולמס פלייס מודיעין': 'מודיעין',
  'הולמס פלייס נהריה': 'נהריה',
  'הולמס פלייס נתניה': 'נתניה',
  'הולמס פלייס עפולה': 'עפולה',
  'הולמס פלייס פתח תקווה': 'פתח תקווה',
  'הולמס פלייס ראשון לציון': 'ראשון לציון',
  'הולמס פלייס רחובות': 'רחובות',
  'הולמס פלייס רמת גן': 'רמת גן',
  'הולמס פלייס רעננה': 'רעננה',
  'הולמס פלייס תל אביב': 'תל אביב'
};

// Assuming classes is an array like [{ name: ..., time: ..., club: ..., region: ... }, ...]
// And regions is a sorted array like ["צפון", "מרכז", "דרום", ...]
// Added clubStatuses to the props
export const ClassList = memo(({ classes = [], regions = [], clubStatuses = {}, openingHours = {} }) => {

  // Group classes by region and day
  const groupedClasses = classes.reduce((acc, cls) => {
    const region = cls.region || 'לא ידוע';
    const day = cls.day_name_hebrew || 'לא ידוע';
    
    if (!acc[region]) {
      acc[region] = {};
    }
    if (!acc[region][day]) {
      acc[region][day] = [];
    }
    
    acc[region][day].push(cls);
    return acc;
  }, {});

  // Sort classes by time within each day
  Object.keys(groupedClasses).forEach(region => {
    Object.keys(groupedClasses[region]).forEach(day => {
      groupedClasses[region][day].sort((a, b) => {
        const timeA = a.time ? a.time.split(':').map(Number) : [0, 0];
        const timeB = b.time ? b.time.split(':').map(Number) : [0, 0];
        return timeA[0] * 60 + timeA[1] - (timeB[0] * 60 + timeB[1]);
      });
    });
  });

  // Extract all clubs from the classes
  const clubsWithData = new Set(classes.map(cls => cls.club));

  // Check for selected clubs with no data due to failed crawls
  const failedSelectedClubs = Object.entries(clubStatuses)
    .filter(([clubName, status]) => 
      status === 'failed' && !clubsWithData.has(clubName)
    )
    .map(([clubName]) => clubName);

  // If there are no classes and no failed clubs, show the empty message
  if ((!classes || classes.length === 0) && failedSelectedClubs.length === 0) {
    return <div className="empty-message">לא נמצאו שיעורים מתאימים</div>;
  }
  
  return (
    <div className="class-list">
      <div className="opening-hours-header">
        <span className="opening-hours-title">שעות פתיחה:</span>
        {Object.entries(openingHours).map(([days, hours]) => (
          <span key={days} className="hours-entry">
            {days} {hours}
          </span>
        ))}
      </div>
      {Object.entries(groupedClasses).map(([region, days]) => (
        <div key={region} className="region-section">
          <h2 className="region-title">{region}</h2>
          {Object.entries(days).map(([day, dayClasses]) => (
            <div key={day} className="day-section">
              <h3 className="day-title">{day}</h3>
              <div className="classes-container">
                {dayClasses.map((cls) => (
                  <div key={`${cls.club}-${cls.time}-${cls.name}`} className="class-card">
                    <div className="class-time">{cls.time}</div>
                    <div className="class-name">{cls.name}</div>
                    <div className="class-instructor">{cls.instructor}</div>
                    <div className="class-club">{clubShortNames[cls.club] || cls.club}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
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
      location: PropTypes.string,
      region: PropTypes.string,
      timestamp: PropTypes.string
  })),
  regions: PropTypes.arrayOf(PropTypes.string),
  clubStatuses: PropTypes.object,
  openingHours: PropTypes.object
}; 