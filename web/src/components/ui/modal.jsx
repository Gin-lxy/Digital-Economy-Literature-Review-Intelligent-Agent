import { cn } from './utils';

export function Modal({ isOpen, title, children, onClose }) {
  if (!isOpen) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black bg-opacity-50 z-40 transition-opacity" onClick={onClose} />

      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className={cn(
            'pointer-events-auto rounded-[2rem] bg-white border border-slate-200 shadow-soft max-w-lg w-full max-h-[80vh] overflow-y-auto'
          )}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="sticky top-0 flex items-center justify-between border-b border-slate-200 bg-slate-50 p-6">
            <h2 className="text-xl font-semibold text-slate-950">{title}</h2>
            <button
              onClick={onClose}
              className="rounded-full p-2 hover:bg-slate-200 transition text-slate-600"
              aria-label="Close"
            >
              X
            </button>
          </div>

          <div className="p-6 text-slate-700 leading-7">{children}</div>
        </div>
      </div>
    </>
  );
}
