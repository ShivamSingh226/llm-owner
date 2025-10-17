import React from 'react';

const CustomButton = ({
  text,
  icon: Icon,
  onClick,
  variant = 'yellow',
  className = '',
}) => {
  const variantClasses = {
    yellow: '!bg-yellow-400 hover:!bg-yellow-500 text-black',
    white: '!bg-white hover:!bg-gray-100 text-black border border-gray-300',
    blue: 'bg-blue-600 text-white hover:bg-blue-700',
  };

  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center px-6 py-2 font-semibold rounded transition ${variantClasses[variant]} ${className}`}
    >
      <Icon fontSize="small" />
      <span className="font-semibold">{text}</span>
    </button>
  );
};

export default CustomButton;
