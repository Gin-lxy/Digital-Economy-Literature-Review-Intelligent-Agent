import { forwardRef } from 'react';
import { cn } from './utils';

export const Input = forwardRef(function Input(props, ref) {
  return (
    <input
      ref={ref}
      className={cn(
        'w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition duration-200 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100'
      )}
      {...props}
    />
  );
});
