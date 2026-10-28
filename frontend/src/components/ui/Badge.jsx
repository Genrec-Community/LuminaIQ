import React from 'react';

export const Badge = React.forwardRef(({ className = '', variant = 'default', children, ...props }, ref) => {
  const baseClasses = "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2";
  
  const variants = {
    default: "border-transparent bg-[#163628] text-[#f4eee2] dark:bg-[#D3EE6A] dark:text-[#0f271c]",
    secondary: "border-transparent bg-[#FDF6F0] text-[#163628] hover:bg-[#E6D5CC] dark:bg-[#182C21] dark:text-[#e8e2dc]",
    destructive: "border-transparent bg-red-500 text-white hover:bg-red-600",
    outline: "text-foreground dark:text-[#e8e2dc] dark:border-white/10",
  };

  return (
    <div
      ref={ref}
      className={`${baseClasses} ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
});

Badge.displayName = "Badge";
