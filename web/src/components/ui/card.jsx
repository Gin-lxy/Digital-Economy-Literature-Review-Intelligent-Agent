import { cn } from './utils';

export function Card({ title, description, actions, className, children }) {
  return (
    <section className={cn('min-w-0 rounded-[1.8rem] border border-slate-200 bg-white p-6 shadow-soft', className)}>
      {(title || description || actions) && (
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="text-lg font-semibold text-slate-950">{title}</h2>}
            {description && <p className="mt-2 text-sm leading-6 text-slate-500">{description}</p>}
          </div>
          {actions && <div>{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}
