import { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface StatusCardProps {
  icon: ReactNode;
  iconBg: 'success' | 'primary' | 'warning' | 'info' | 'error';
  label: string;
  value: string | number;
  subValue?: string;
}

export function StatusCard({ icon, iconBg, label, value, subValue }: StatusCardProps) {
  const iconBgClasses = {
    success: 'bg-success/10 text-success',
    primary: 'bg-primary/10 text-primary',
    warning: 'bg-warning/10 text-warning',
    info: 'bg-info/10 text-info',
    error: 'bg-destructive/10 text-destructive',
  };

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm transition-shadow hover:shadow-md">
      <div className={cn('inline-flex h-10 w-10 items-center justify-center rounded-lg', iconBgClasses[iconBg])}>
        {icon}
      </div>
      <p className="mt-3 text-xs font-medium text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-bold text-foreground">{value}</p>
      {subValue && <p className="mt-0.5 text-xs text-muted-foreground">{subValue}</p>}
    </div>
  );
}
