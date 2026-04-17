import { cn } from './utils';

const variants = {
  default: 'bg-slate-100 text-slate-700',
  info: 'bg-indigo-100 text-indigo-700',
  success: 'bg-emerald-100 text-emerald-700',
};

export function Badge({ variant = 'default', className, children }) {
  return (
    <span className={cn('inline-flex rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em]', variants[variant], className)}>
      {children}
    </span>
  );
}
