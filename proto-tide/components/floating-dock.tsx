import Link from 'next/link';

const actions = [
  { href: '/', label: '首页', icon: '🏠' },
  { href: '/discover', label: '发现', icon: '🧭' },
  { href: '/rankings', label: '热榜', icon: '🔥' },
  { href: '/game/starfall-zero', label: '焦点', icon: '✨' }
];

export function FloatingDock() {
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-5 z-50 flex justify-center px-4 md:bottom-7">
      <div className="floating-dock pointer-events-auto flex items-center gap-2 rounded-full px-3 py-3 text-sm text-white/82 shadow-[0_20px_60px_rgba(0,0,0,0.38)]">
        {actions.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="flex items-center gap-2 rounded-full px-4 py-2 transition hover:bg-white/10 hover:text-white"
          >
            <span>{item.icon}</span>
            <span className="hidden sm:inline">{item.label}</span>
          </Link>
        ))}
        <button className="ml-1 rounded-full bg-[linear-gradient(135deg,#23d3a2,#6df0cf)] px-4 py-2 font-semibold text-slate-950 transition hover:scale-[1.03]">
          发个状态
        </button>
      </div>
    </div>
  );
}
