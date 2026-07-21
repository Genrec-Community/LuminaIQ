import React from 'react';

export const Button = React.forwardRef(({ className = '', variant = 'default', size = 'default', asChild = false, children, ...props }, ref) => {
  const baseClasses = "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50";
  
  const variants = {
    default: "bg-[#a08072] text-white shadow hover:bg-[#8a6a5c] dark:bg-[#720760] dark:text-white dark:hover:bg-[#620960]",
    destructive: "bg-red-500 text-white shadow-sm hover:bg-red-600",
    outline: "border border-[#E6D5CC] bg-transparent shadow-sm hover:bg-[#E6D5CC]/50 hover:text-inherit dark:border-white/10 dark:hover:bg-white/10",
    secondary: "bg-[#FDF6F0] text-[#4A3B32] shadow-sm hover:bg-[#E6D5CC] dark:bg-[#252018] dark:text-[#e8e2dc] dark:hover:bg-[#342e26]",
    ghost: "hover:bg-[#E6D5CC]/30 hover:text-inherit dark:hover:bg-white/10",
    link: "text-[#a08072] underline-offset-4 hover:underline dark:text-[#d4aa82]",
  };
  
  const sizes = {
    default: "h-9 px-4 py-2",
    sm: "h-8 rounded-md px-3 text-xs",
    lg: "h-10 rounded-md px-8",
    icon: "h-9 w-9",
  };

  const Component = asChild ? (
    React.Children.only(children)
  ) : (
    <button
      className={`${baseClasses} ${variants[variant]} ${sizes[size]} ${className}`}
      ref={ref}
      {...props}
    >
      {children}
    </button>
  );

  if (asChild) {
    return React.cloneElement(Component, {
      ...props,
      className: `${baseClasses} ${variants[variant]} ${sizes[size]} ${className} ${Component.props.className || ''}`,
      ref,
    });
  }

  return Component;
});

Button.displayName = "Button";
