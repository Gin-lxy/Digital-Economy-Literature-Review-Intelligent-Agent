import { cn } from './utils';

const variants = {
  default: 'bg-slate-900 text-white shadow-sm hover:bg-slate-800',
  secondary: 'bg-white text-slate-900 border border-slate-200 hover:bg-slate-50',
  accent: 'bg-indigo-600 text-white shadow-sm hover:bg-indigo-500',
  subtle: 'bg-slate-100 text-slate-700 hover:bg-slate-200',
};

export function Button({ variant = 'default', className, ...props }) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-full px-5 py-2.5 text-sm font-semibold transition duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-200',
        variants[variant],
        className
      )}
      {...props}
    />
  );
}
