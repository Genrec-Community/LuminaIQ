import React from 'react';

// Base skeleton component with pulse animation
export const Skeleton = ({ className = '', ...props }) => (
  <div 
    className={`animate-pulse bg-gradient-to-r from-[#E6D5CC] via-[#F5EDE6] to-[#E6D5CC] bg-[length:200%_100%] ${className}`}
    {...props}
  />
);

// Card skeleton
export const CardSkeleton = ({ className = '' }) => (
  <div className={`bg-white rounded-2xl border border-[#E6D5CC] p-6 ${className}`}>
    <Skeleton className="h-12 w-12 rounded-xl mb-4" />
    <Skeleton className="h-6 w-3/4 mb-2" />
    <Skeleton className="h-4 w-1/2" />
  </div>
);

// Stats card skeleton
export const StatsCardSkeleton = ({ className = '' }) => (
  <div className={`bg-white rounded-2xl border border-[#E6D5CC] p-6 ${className}`}>
    <div className="flex items-center justify-between mb-4">
      <Skeleton className="h-10 w-10 rounded-lg" />
      <Skeleton className="h-8 w-8 rounded-full" />
    </div>
    <Skeleton className="h-8 w-16 mb-2" />
    <Skeleton className="h-4 w-24" />
  </div>
);

// List item skeleton
export const ListItemSkeleton = ({ className = '' }) => (
  <div className={`flex items-center gap-4 p-4 ${className}`}>
    <Skeleton className="h-10 w-10 rounded-lg" />
    <div className="flex-1">
      <Skeleton className="h-4 w-3/4 mb-2" />
      <Skeleton className="h-3 w-1/2" />
    </div>
  </div>
);

// Chart skeleton
export const ChartSkeleton = ({ className = '' }) => (
  <div className={`bg-white rounded-2xl border border-[#E6D5CC] p-6 ${className}`}>
    <Skeleton className="h-6 w-32 mb-4" />
    <div className="flex items-end gap-2 h-40">
      {[...Array(7)].map((_, i) => (
        <Skeleton 
          key={i} 
          className="flex-1 rounded-t" 
          style={{ height: `${30 + Math.random() * 50}%` }}
        />
      ))}
    </div>
  </div>
);

// Table skeleton
export const TableSkeleton = ({ rows = 5, className = '' }) => (
  <div className={`bg-white rounded-2xl border border-[#E6D5CC] overflow-hidden ${className}`}>
    <div className="bg-[#FDF6F0] border-b border-[#E6D5CC] p-4">
      <div className="flex gap-4">
        <Skeleton className="h-4 w-1/4" />
        <Skeleton className="h-4 w-1/4" />
        <Skeleton className="h-4 w-1/4" />
        <Skeleton className="h-4 w-1/4" />
      </div>
    </div>
    {[...Array(rows)].map((_, i) => (
      <div key={i} className="p-4 border-b border-[#E6D5CC] last:border-0">
        <div className="flex gap-4">
          <Skeleton className="h-4 w-1/4" />
          <Skeleton className="h-4 w-1/4" />
          <Skeleton className="h-4 w-1/4" />
          <Skeleton className="h-4 w-1/4" />
        </div>
      </div>
    ))}
  </div>
);

// Document card skeleton
export const DocumentCardSkeleton = ({ className = '' }) => (
  <div className={`flex items-center gap-4 p-4 bg-white rounded-xl border border-[#E6D5CC] ${className}`}>
    <Skeleton className="h-10 w-10 rounded-lg" />
    <div className="flex-1">
      <Skeleton className="h-4 w-3/4 mb-2" />
      <Skeleton className="h-3 w-1/3" />
    </div>
    <Skeleton className="h-8 w-8 rounded-lg" />
  </div>
);

// Progress bar skeleton
export const ProgressBarSkeleton = ({ className = '' }) => (
  <div className={className}>
    <div className="flex justify-between mb-2">
      <Skeleton className="h-4 w-20" />
      <Skeleton className="h-4 w-12" />
    </div>
    <Skeleton className="h-2 w-full rounded-full" />
  </div>
);

// Avatar skeleton
export const AvatarSkeleton = ({ size = 'md', className = '' }) => {
  const sizes = {
    sm: 'h-8 w-8',
    md: 'h-10 w-10',
    lg: 'h-12 w-12',
    xl: 'h-16 w-16'
  };
  return <Skeleton className={`${sizes[size]} rounded-full ${className}`} />;
};

// Badge skeleton
export const BadgeSkeleton = ({ className = '' }) => (
  <Skeleton className={`h-6 w-16 rounded-full ${className}`} />
);

// Button skeleton
export const ButtonSkeleton = ({ className = '' }) => (
  <Skeleton className={`h-10 w-24 rounded-lg ${className}`} />
);

// Input skeleton
export const InputSkeleton = ({ className = '' }) => (
  <Skeleton className={`h-10 w-full rounded-lg ${className}`} />
);

// Tabs skeleton
export const TabsSkeleton = ({ className = '' }) => (
  <div className={`flex gap-2 ${className}`}>
    <Skeleton className="h-8 w-20 rounded-lg" />
    <Skeleton className="h-8 w-20 rounded-lg" />
    <Skeleton className="h-8 w-20 rounded-lg" />
  </div>
);

// Dashboard skeleton - comprehensive layout
export const DashboardSkeleton = () => (
  <div className="min-h-screen bg-[#FDF6F0] font-sans text-[#4A3B32]">
    {/* Header */}
    <header className="bg-white border-b border-[#E6D5CC] sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-10 rounded-xl" />
          <Skeleton className="h-8 w-32" />
        </div>
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10 rounded-full" />
          <Skeleton className="h-10 w-10 rounded-lg" />
        </div>
      </div>
    </header>

    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Welcome Section */}
      <div className="mb-8">
        <Skeleton className="h-9 w-64 mb-2" />
        <Skeleton className="h-5 w-96" />
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatsCardSkeleton />
        <StatsCardSkeleton />
        <StatsCardSkeleton />
        <StatsCardSkeleton />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Projects */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-2xl border border-[#E6D5CC] p-6">
            <div className="flex items-center justify-between mb-6">
              <Skeleton className="h-6 w-40" />
              <Skeleton className="h-8 w-24 rounded-lg" />
            </div>
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <ListItemSkeleton key={i} />
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-[#E6D5CC] p-6">
            <Skeleton className="h-6 w-32 mb-4" />
            <ProgressBarSkeleton />
            <Skeleton className="h-4 w-24 mt-4" />
          </div>
          
          <div className="bg-white rounded-2xl border border-[#E6D5CC] p-6">
            <Skeleton className="h-6 w-32 mb-4" />
            <div className="space-y-2">
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="flex items-center gap-2">
                  <Skeleton className="h-4 w-4 rounded" />
                  <Skeleton className="h-4 w-20" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
);

// Project View skeleton
export const ProjectViewSkeleton = () => (
  <div className="min-h-screen bg-[#FDF6F0] font-sans text-[#4A3B32]">
    {/* Sidebar */}
    <div className="fixed left-0 top-0 h-full w-64 bg-white border-r border-[#E6D5CC] p-4">
      <Skeleton className="h-10 w-10 rounded-xl mb-6" />
      <div className="space-y-2">
        {[1, 2, 3, 4, 5, 6].map(i => (
          <div key={i} className="flex items-center gap-3 p-3">
            <Skeleton className="h-5 w-5 rounded" />
            <Skeleton className="h-4 w-24" />
          </div>
        ))}
      </div>
    </div>

    {/* Main Content */}
    <div className="ml-64 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Skeleton className="h-9 w-64 mb-2" />
          <Skeleton className="h-5 w-96" />
        </div>

        {/* Tabs */}
        <TabsSkeleton className="mb-6" />

        {/* Content Area */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <div className="bg-white rounded-2xl border border-[#E6D5CC] p-6">
              <Skeleton className="h-6 w-40 mb-4" />
              <div className="space-y-3">
                {[1, 2, 3].map(i => (
                  <DocumentCardSkeleton key={i} />
                ))}
              </div>
            </div>
          </div>
          
          <div>
            <ChartSkeleton />
          </div>
        </div>
      </div>
    </div>
  </div>
);

export default {
  Skeleton,
  CardSkeleton,
  StatsCardSkeleton,
  ListItemSkeleton,
  ChartSkeleton,
  TableSkeleton,
  DocumentCardSkeleton,
  ProgressBarSkeleton,
  AvatarSkeleton,
  BadgeSkeleton,
  ButtonSkeleton,
  InputSkeleton,
  TabsSkeleton,
  DashboardSkeleton,
  ProjectViewSkeleton
};
