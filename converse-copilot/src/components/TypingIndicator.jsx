import React from 'react';

function TypingIndicator() {
  const dotStyle = {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    backgroundColor: '#a0a0a0',
    display: 'inline-block',
    marginRight: '4px',
    animation: 'bounceColor 0.6s infinite ease-in-out',
  };

  return (
    <div className="flex items-end gap-1 h-6">
      <span style={dotStyle}></span>
      <span style={{ ...dotStyle, animationDelay: '0.1s' }}></span>
      <span style={{ ...dotStyle, animationDelay: '0.2s' }}></span>

      <style>
        {`
          @keyframes bounceColor {
            0%, 80%, 100% { transform: translateY(0); background-color: #a0a0a0; }
            40% { transform: translateY(-6px); background-color: #4b4b4b; }
          }
        `}
      </style>
    </div>
  );
}

export default TypingIndicator;
