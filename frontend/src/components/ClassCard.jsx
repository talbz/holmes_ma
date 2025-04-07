import { memo } from 'react';
import classNames from 'classnames';
import PropTypes from 'prop-types';

export const ClassCard = memo(({ classItem }) => {
  const { className, instructor, day, time, duration, club } = classItem;
  
  return (
    <div className="class-card">
      <h3>{className}</h3>
      {instructor && <p><strong>מדריך:</strong> {instructor}</p>}
      <p><strong>יום:</strong> {day}</p>
      <p><strong>שעה:</strong> {time}</p>
      {duration && <p><strong>משך:</strong> {duration}</p>}
      {club && <p><strong>סניף:</strong> {club}</p>}
    </div>
  );
});

ClassCard.displayName = 'ClassCard';

ClassCard.propTypes = {
  classItem: PropTypes.shape({
    className: PropTypes.string.isRequired,
    instructor: PropTypes.string,
    day: PropTypes.string.isRequired,
    time: PropTypes.string.isRequired,
    duration: PropTypes.string,
    club: PropTypes.string,
  }).isRequired,
}; 