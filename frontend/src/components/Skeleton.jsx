import React from 'react';
import { FileText, Loader2 } from 'lucide-react';
import Logo from './brand/Logo';
import SidebarNav from './SidebarNav';

// Placeholder in the app's own palette: a faint forest tint with a slow highlight sweep
export const Shimmer = ({ className = '', style }) => (
  <div className={`lumina-shimmer ${className}`} style={style} aria-hidden="true" />
);

// One calm status line for waits; after a few seconds it explains the longer first load
export const LoadingNote = ({ slow = false, className = '', children }) => (
  <p className={`flex items-center gap-2.5 text-sm text-[#5E5046] ${className}`} role="status">
    <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[#1E5C42]" />
    <span>
      {children}
      {slow ? <span className="text-[#5E5046]/80">. The first visit after a quiet spell can take up to a minute.</span> : '…'}
    </span>
  </p>
);

// A book card while the shelf loads: same shape as the real one on the dashboard
export const BookCardSkeleton = () => (
  <div className="rounded-[1.25rem] border border-[#163628]/10 bg-white p-6" aria-hidden="true">
    <Shimmer className="mb-8 h-12 w-12 rounded-2xl" />
    <Shimmer className="h-6 w-3/4 rounded-lg" />
    <div className="mt-4 flex gap-4 border-t border-[#FDF6F0] pt-4">
      <Shimmer className="h-4 w-24 rounded-full" />
      <Shimmer className="h-4 w-16 rounded-full" />
    </div>
  </div>
);

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
  <div className="min-h-screen bg-[#FDF6F0] font-sans text-[#163628]">
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

// Project View skeleton: the workspace itself (logo, the real tool list, header, documents
// panel) with soft placeholders only where the book's own data will land.
export const ProjectViewSkeleton = ({ slow = false }) => (
  <div className="flex h-screen overflow-hidden" style={{ background: 'var(--th-alt, #FDF6F0)' }} aria-busy="true">
    <aside className="hidden md:flex w-80 shrink-0 flex-col border-r border-[#163628]/10 px-4 pt-5 pb-3">
      <div className="mb-6 px-1.5"><Logo /></div>
      <div className="flex-1 min-h-0 overflow-hidden pointer-events-none opacity-60" aria-hidden="true">
        <SidebarNav activeTab="" onSelect={() => {}} collapsed={false} isDark={false} aiLabel="Lumi" />
      </div>
      <div className="flex items-center gap-3 border-t border-[#163628]/10 px-3 pt-4">
        <Shimmer className="h-10 w-10 rounded-full" />
        <div className="flex-1"><Shimmer className="h-3.5 w-24 rounded-full" /><Shimmer className="mt-2 h-3 w-12 rounded-full" /></div>
      </div>
    </aside>

    <div className="flex-1 min-w-0 flex flex-col" style={{ background: 'color-mix(in srgb, var(--th-surface, #ffffff) 50%, transparent)' }}>
      <div className="flex h-[3.75rem] items-center gap-3 border-b border-[#163628]/10 px-5">
        <Shimmer className="h-5 w-40 rounded-full" />
      </div>
      <div className="flex-1 overflow-hidden px-6 py-10 md:px-10">
        <div className="max-w-3xl">
          <Shimmer className="h-12 w-3/5 rounded-xl md:h-14" />
          <Shimmer className="mt-5 h-5 w-4/5 rounded-full" />
          <Shimmer className="mt-3 h-5 w-2/3 rounded-full" />
          <div className="mt-10 rounded-[1.25rem] border border-[#163628]/10 bg-white/70 p-6">
            <Shimmer className="h-4 w-32 rounded-full" />
            <Shimmer className="mt-4 h-11 w-full rounded-xl" />
          </div>
          <LoadingNote slow={slow} className="mt-8">Opening your book</LoadingNote>
        </div>
      </div>
    </div>

    <aside className="hidden lg:flex w-80 shrink-0 flex-col border-l border-[#163628]/10 p-4">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#163628]/90 text-[#D3EE6A]"><FileText className="h-5 w-5" /></div>
        <div><p className="text-sm font-bold text-[#163628] leading-tight">Documents</p><Shimmer className="mt-1.5 h-3 w-16 rounded-full" /></div>
      </div>
      <Shimmer className="h-10 w-full rounded-full" />
      <div className="mt-5 space-y-3">
        {[0, 1, 2].map(i => (
          <div key={i} className="flex items-center gap-3 rounded-xl border border-[#163628]/10 bg-white/70 p-3">
            <Shimmer className="h-8 w-8 rounded-lg" />
            <div className="flex-1"><Shimmer className="h-3.5 w-4/5 rounded-full" /><Shimmer className="mt-2 h-3 w-1/3 rounded-full" /></div>
          </div>
        ))}
      </div>
    </aside>
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
  ProjectViewSkeleton,
  BookCardSkeleton,
  Shimmer,
  LoadingNote
};
